import os
import json
import sqlite3
import re
import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

DB = "data/skillsprint.db"

st.set_page_config(
    page_title="SkillSprint",
    page_icon="⚡",
    layout="wide"
)


# DATABASE

def connect():
    os.makedirs("data", exist_ok=True)
    c = sqlite3.connect(DB, check_same_thread=False)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions(
            id INTEGER PRIMARY KEY,
            created_at TEXT,
            role TEXT,
            level TEXT,
            category TEXT,
            score REAL,
            results TEXT
        )
    """)

    c.commit()
    return c


def history():
    c = connect()
    d = pd.read_sql_query(
        "SELECT * FROM sessions ORDER BY id DESC", c
    )
    c.close()
    return d


def save(role, level, category, results):
    score = round(
        sum(r["score"] for r in results) / len(results), 1
    )

    c = connect()

    c.execute(
        """INSERT INTO sessions
        (created_at, role, level, category, score, results)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            role,
            level,
            category,
            score,
            json.dumps(results)
        )
    )

    c.commit()
    c.close()


# AI INTEGRATION


def ai(prompt, system):
    provider = st.session_state.provider

    if provider == "Gemini":
        key = os.getenv("GEMINI_API_KEY", "").strip()

        if not key:
            raise RuntimeError("Gemini API key is missing.")

        from google import genai

        client = genai.Client(api_key=key)
        response = None

        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                    contents=system + "\n\n" + prompt
                )
                break

            except Exception as e:
                error_message = str(e).upper()

                temporary_error = any(
                    code in error_message
                    for code in [
                        "503",
                        "UNAVAILABLE",
                        "429",
                        "RESOURCE_EXHAUSTED",
                        "500",
                        "INTERNAL"
                    ]
                )

                if not temporary_error or attempt == 2:
                    raise

                wait_seconds = 2 ** (attempt + 1)
                time.sleep(wait_seconds)

        if not response.text:
            raise RuntimeError("Gemini returned an empty response.")

        return response.text

    elif provider == "Claude":
        key = os.getenv("ANTHROPIC_API_KEY", "").strip()

        if not key:
            raise RuntimeError("Claude API key is missing.")

        import anthropic

        client = anthropic.Anthropic(api_key=key)

        msg = client.messages.create(
            model=os.getenv(
                "CLAUDE_MODEL",
                "claude-haiku-4-5-20251001"
            ),
            max_tokens=1800,
            system=system,
            messages=[{"role": "user", "content": prompt}]
        )

        answer = "".join(
            item.text for item in msg.content
            if getattr(item, "type", "") == "text"
        )

        if not answer:
            raise RuntimeError("Claude returned an empty response.")

        return answer

    else:
        raise ValueError(f"Unsupported AI provider: {provider}")


# JSON PROCESSING

def as_json(s):
    s = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        s.strip()
    )

    a = s.find("{")
    b = s.rfind("}")

    if a < 0 or b <= a:
        raise ValueError("AI did not return valid JSON.")

    return json.loads(s[a:b + 1])


# QUESTION GENERATION

def questions(role, level, category, jd, n):
    prompt = f"""
Create exactly {n} realistic interview questions for:

Role: {role}
Experience level: {level}
Category: {category}
Job description: {jd or 'Not supplied'}

Return ONLY valid JSON in this format:

{{
  "questions": [
    {{
      "topic": "Python",
      "question": "Your question here",
      "difficulty": "Easy"
    }}
  ]
}}
"""

    result = as_json(
        ai(
            prompt,
            "You generate realistic interview questions. Return valid JSON only."
        )
    )

    generated = result.get("questions", [])

    if not generated:
        raise ValueError("No questions were generated.")

    return generated[:n]


# ANSWER EVALUATION

def evaluate(q, answer, role, level):
    prompt = f"""
Evaluate this interview answer fairly.

Role: {role}
Experience level: {level}
Question: {q}
Candidate answer: {answer}

Score each category from 0 to 10:

1. technical_accuracy
2. relevance
3. completeness
4. clarity

Return ONLY valid JSON with these keys:

technical_accuracy
relevance
completeness
clarity
strengths (array)
missing_points (array)
feedback
improved_answer
"""

    data = as_json(
        ai(
            prompt,
            "You are a fair interview evaluator. Return valid JSON only."
        )
    )

    for key in [
        "technical_accuracy",
        "relevance",
        "completeness",
        "clarity"
    ]:
        data[key] = max(
            0,
            min(10, float(data.get(key, 0)))
        )

    data["score"] = round(
        sum(
            data[key]
            for key in [
                "technical_accuracy",
                "relevance",
                "completeness",
                "clarity"
            ]
        ) * 2.5,
        1
    )

    data.setdefault("strengths", [])
    data.setdefault("missing_points", [])
    data.setdefault("feedback", "Evaluation completed.")
    data.setdefault("improved_answer", "Review the feedback above.")

    return data


# DEMO QUESTIONS

DEMO = {
    "Technical": [
        {
            "topic": "Python",
            "question": "What is the difference between a list and a tuple in Python?",
            "difficulty": "Easy"
        },
        {
            "topic": "OOP",
            "question": "Explain encapsulation with a practical example.",
            "difficulty": "Medium"
        },
        {
            "topic": "SQL",
            "question": "What is the difference between WHERE and HAVING?",
            "difficulty": "Medium"
        },
        {
            "topic": "DSA",
            "question": "How would you find the second largest element in an array?",
            "difficulty": "Medium"
        }
    ],

    "Behavioral": [
        {
            "topic": "Teamwork",
            "question": "Tell me about a time you worked with others to complete a task.",
            "difficulty": "Easy"
        },
        {
            "topic": "Problem solving",
            "question": "Describe a difficult problem you faced and how you approached it.",
            "difficulty": "Medium"
        },
        {
            "topic": "Adaptability",
            "question": "How do you respond to feedback or learning something quickly?",
            "difficulty": "Easy"
        }
    ],

    "Mixed": [
        {
            "topic": "Introduction",
            "question": "Tell me about yourself and why you are interested in this role.",
            "difficulty": "Easy"
        },
        {
            "topic": "Technical",
            "question": "Explain one technical concept you recently learned and where it is useful.",
            "difficulty": "Easy"
        },
        {
            "topic": "Problem solving",
            "question": "How would you approach a problem you have never seen before?",
            "difficulty": "Medium"
        },
        {
            "topic": "Teamwork",
            "question": "Tell me about a time you worked with a team to solve a problem.",
            "difficulty": "Medium"
        }
    ]
}


# DEMO EVALUATION

def demo_eval(answer):
    n = len(answer.strip())
    score = 4 if n < 35 else 6 if n < 100 else 7

    return {
        "technical_accuracy": score,
        "relevance": score,
        "completeness": max(2, score - 1),
        "clarity": score,

        "score": round(
            (score * 3 + max(2, score - 1)) * 2.5,
            1
        ),

        "strengths": [
            "You attempted the question."
        ],

        "missing_points": [
            "Add a concrete example.",
            "Explain your reasoning."
        ],

        "feedback": (
            "DEMO MODE: this feedback is based on answer "
            "length, not semantic AI evaluation."
        ),

        "improved_answer": (
            "Use a definition, explain the key idea, "
            "and give a relevant example."
        )
    }


# SESSION STATE

defaults = {
    "page": "Dashboard",
    "provider": "Claude",
    "questions": [],
    "answers": {},
    "evaluations": {},
    "idx": 0,
    "active": False,
    "done": False,
    "role": "Software Developer",
    "level": "Fresher",
    "category": "Mixed",
    "jd": "",
    "mode": "",
    "last_results": []
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# CUSTOM DESIGN

st.markdown("""
<style>
.block-container {
    max-width: 1150px;
    padding-top: 1.5rem;
}

.hero {
    padding: 24px;
    border-radius: 15px;
    background: linear-gradient(110deg, #14213d, #315b91);
    color: white;
}

.hero h1 {
    color: white;
}
</style>
""", unsafe_allow_html=True)


# SIDEBAR

with st.sidebar:
    st.markdown("## ⚡ SkillSprint")
    st.caption("Your personal AI interview coach")

    pages = [
        "Dashboard",
        "Start Practice",
        "Performance",
        "About"
    ]

    st.session_state.page = st.radio(
        "MENU",
        pages,
        index=pages.index(st.session_state.page)
    )

    st.divider()

    st.session_state.provider = st.selectbox(
        "AI provider",
        ["Claude", "Gemini"],
        index=0 if st.session_state.provider == "Claude" else 1
    )

    st.caption("Keep API keys in .env. Never commit them.")

    if st.button("Reset practice"):
        st.session_state.questions = []
        st.session_state.answers = {}
        st.session_state.evaluations = {}
        st.session_state.active = False
        st.session_state.done = False
        st.session_state.idx = 0

        st.rerun()


page = st.session_state.page


# DASHBOARD

if page == "Dashboard":
    st.markdown(
        '<div class="hero"><h1>Welcome to SkillSprint ⚡</h1>'
        '<p>Practise smarter. Identify gaps. Improve with every session.</p></div>',
        unsafe_allow_html=True
    )

    d = history()
    total = len(d)

    a, b, c = st.columns(3)

    a.metric("Practice sessions", total)

    b.metric(
        "Average score",
        f"{d.score.mean():.1f}/100" if total else "—"
    )

    c.metric(
        "Best score",
        f"{d.score.max():.1f}/100" if total else "—"
    )

    x, y = st.columns([1.2, 1])

    with x:
        st.subheader("Prepare for your target role")

        st.write(
            "Generate tailored questions, practise answers "
            "and receive structured feedback."
        )

        if st.button("Start a mock interview", type="primary"):
            st.session_state.page = "Start Practice"
            st.rerun()

    with y:
        st.subheader("How it works")

        st.write(
            "1. Choose a role and interview type\n\n"
            "2. Practise questions\n\n"
            "3. Receive rubric-based feedback\n\n"
            "4. Review skill gaps and progress"
        )

    st.subheader("Recent sessions")

    if total:
        st.text(
            d[
                ["created_at", "role", "category", "score"]
            ].head().to_string(index=False)
        )
    else:
        st.info(
            "No sessions yet. Start your first practice session."
        )


# START PRACTICE

elif page == "Start Practice":
    st.title("🎤 Interview Practice")

    # INTERVIEW SETUP

    if not st.session_state.active and not st.session_state.done:
        with st.form("setup"):
            st.session_state.role = st.text_input(
                "Target job role",
                st.session_state.role
            )

            st.session_state.level = st.selectbox(
                "Experience level",
                ["Fresher", "0–2 years", "2–5 years"]
            )

            st.session_state.category = st.selectbox(
                "Interview category",
                ["Mixed", "Technical", "Behavioral"]
            )

            count = st.selectbox(
                "Number of questions",
                [3, 4, 5],
                index=1
            )

            st.session_state.jd = st.text_area(
                "Job description (optional)",
                st.session_state.jd,
                height=120
            )

            go = st.form_submit_button(
                "Generate questions",
                type="primary",
                use_container_width=True
            )

        if go:
            with st.spinner("Preparing your interview..."):
                try:
                    st.session_state.questions = questions(
                        st.session_state.role,
                        st.session_state.level,
                        st.session_state.category,
                        st.session_state.jd,
                        count
                    )

                    st.session_state.mode = "LIVE AI"

                except Exception:
                    st.session_state.questions = (
                        DEMO[st.session_state.category] * 2
                    )[:count]

                    st.session_state.mode = "DEMO"

                st.session_state.answers = {}
                st.session_state.evaluations = {}
                st.session_state.idx = 0
                st.session_state.active = True

                st.rerun()


    # ACTIVE INTERVIEW

    elif st.session_state.active:
        qs = st.session_state.questions
        i = st.session_state.idx
        q = qs[i]

        st.progress(
            (i + 1) / len(qs),
            text=(
                f"Question {i + 1} of {len(qs)} · "
                f"{st.session_state.mode}"
            )
        )

        if st.session_state.mode == "DEMO":
            st.caption("Sample questions are being used.")

        st.caption(
            f"{q.get('topic', 'Interview')} · "
            f"{q.get('difficulty', 'General')}"
        )

        st.subheader(q["question"])

        ans = st.text_area(
            "Your answer",
            st.session_state.answers.get(i, ""),
            height=170,
            key=f"ans{i}",
            placeholder="Write your answer. Include reasoning and an example."
        )

        st.session_state.answers[i] = ans

        prev, nxt = st.columns(2)

        with prev:
            if i > 0 and st.button("← Previous"):
                st.session_state.idx -= 1
                st.rerun()

        with nxt:
            button_text = (
                "Evaluate & continue"
                if i < len(qs) - 1
                else "Evaluate final answer"
            )

            if st.button(
                button_text,
                type="primary",
                use_container_width=True
            ):
                if not ans.strip():
                    st.error("Please enter an answer first.")

                else:
                    with st.spinner("Evaluating your answer..."):
                        try:
                            ev = evaluate(
                                q["question"],
                                ans,
                                st.session_state.role,
                                st.session_state.level
                            )

                        except Exception:
                            ev = demo_eval(ans)

                        st.session_state.evaluations[i] = ev

                    if i < len(qs) - 1:
                        st.session_state.idx += 1
                        st.rerun()

                    else:
                        results = []

                        for j, qq in enumerate(qs):
                            ev = st.session_state.evaluations.get(
                                j,
                                demo_eval(
                                    st.session_state.answers.get(j, "")
                                )
                            )

                            results.append({
                                "topic": qq.get("topic", "General"),
                                "question": qq["question"],
                                "answer": st.session_state.answers.get(j, ""),
                                **ev
                            })

                        save(
                            st.session_state.role,
                            st.session_state.level,
                            st.session_state.category,
                            results
                        )

                        st.session_state.last_results = results
                        st.session_state.active = False
                        st.session_state.done = True

                        st.rerun()


    # COMPLETED INTERVIEW

    else:
        st.success("Practice session completed!")

        rs = st.session_state.get("last_results", [])

        if rs:
            average = sum(
                r["score"] for r in rs
            ) / len(rs)

            st.metric(
                "Session score",
                f"{average:.1f}/100"
            )

            for i, r in enumerate(rs, 1):
                with st.expander(
                    f"Question {i}: {r['topic']} · {r['score']}/100"
                ):
                    st.write("**Your answer:**", r["answer"])

                    st.write("**Feedback:**", r["feedback"])

                    st.write(
                        "**Strengths:**",
                        ", ".join(r["strengths"])
                    )

                    st.write(
                        "**Improve:**",
                        ", ".join(r["missing_points"])
                    )

                    st.write(
                        "**Suggested answer:**",
                        r["improved_answer"]
                    )

            st.subheader("Recommended next steps")

            gaps = list(dict.fromkeys(
                g
                for r in rs
                for g in r["missing_points"]
            ))

            for g in gaps[:6]:
                st.write("• " + g)

        if st.button("Start another session", type="primary"):
            st.session_state.done = False
            st.session_state.questions = []
            st.session_state.answers = {}
            st.session_state.evaluations = {}

            st.rerun()


# PERFORMANCE

elif page == "Performance":
    st.title("📊 Performance & Skill Gaps")

    d = history()

    if d.empty:
        st.info(
            "Complete a session to unlock your performance dashboard."
        )

    else:
        a, b, c = st.columns(3)

        a.metric("Sessions", len(d))

        b.metric(
            "Average",
            f"{d.score.mean():.1f}/100"
        )

        c.metric(
            "Latest",
            f"{d.score.iloc[0]:.1f}/100"
        )

        fig = px.line(
            d.sort_values("id"),
            x="created_at",
            y="score",
            markers=True,
            labels={
                "created_at": "Date",
                "score": "Score"
            }
        )

        fig.update_yaxes(range=[0, 100])

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        st.subheader("Practice history")

        st.text(
            d[
                ["created_at", "role", "level", "category", "score"]
            ].to_string(index=False)
        )

        st.subheader("Latest improvement areas")

        latest = json.loads(d.iloc[0]["results"])

        gaps = list(dict.fromkeys(
            g
            for r in latest
            for g in r.get("missing_points", [])
        ))

        for g in gaps[:8]:
            st.write("• " + g)


# ABOUT

else:
    st.title("About SkillSprint")

    st.write(
        "SkillSprint is an AI-powered interview preparation "
        "assistant for students and job seekers."
    )

    st.markdown("""
    **Features:** role-based question generation, job-description context,
    text mock interviews, rubric-based answer evaluation, strengths and
    missing concepts, improvement suggestions, skill-gap recommendations
    and saved progress.

    **AI integration:** The app sends the role, context, question and
    candidate answer to an existing Gemini or Claude LLM API.
    It does not train its own model.

    **Evaluation rubric:** technical accuracy, relevance,
    completeness and clarity.

    Scores are advisory and may be imperfect. Demo mode uses
    sample questions and simple placeholder feedback only;
    it is not live AI evaluation.
    """)
