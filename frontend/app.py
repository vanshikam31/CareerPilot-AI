import pandas as pd
import streamlit as st

from api import APIError, request, wake_server

st.set_page_config(page_title="CareerPilot AI", page_icon="🧭", layout="wide")

LEVELS = ["fresher", "junior", "mid", "senior"]


# ---------- helpers ----------
def pct(value) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def split_list(text: str) -> list[str]:
    return [p.strip() for p in text.replace("\n", ",").split(",") if p.strip()]


def call(method: str, path: str, **kwargs):
    """API call with the logged-in token. An expired token sends the user back to login."""
    try:
        return request(method, path, token=st.session_state.get("token"), **kwargs)
    except APIError as exc:
        if exc.status == 401 and st.session_state.get("token"):
            st.session_state.clear()
            st.session_state["notice"] = "Your session expired. Please log in again."
            st.rerun()
        raise


def job_card(job: dict, score: float | None = None, details=None) -> None:
    with st.container(border=True):
        main, side = st.columns([5, 1])
        main.markdown(f"**{job['title']}** · {job['company']}")
        main.caption(
            f"📍 {job['location']} · {job['work_mode']} · {job['experience_level']} · job #{job['id']}"
        )
        if score is not None:
            side.metric("Match", f"{score:.0%}")
        st.write(" ".join(f"`{s}`" for s in job["skills"]))
        if details:
            details()


# ---------- login ----------
def do_login(email: str, password: str) -> None:
    with st.spinner("Contacting the server (a sleeping free server can take about a minute)..."):
        wake_server()
        try:
            data = request("POST", "/api/auth/login", data={"username": email, "password": password})
            me = request("GET", "/api/users/me", token=data["access_token"])
        except APIError as exc:
            st.error(str(exc))
            return
    st.session_state.update(token=data["access_token"], name=me["full_name"])
    st.rerun()


def auth_page() -> None:
    st.title("🧭 CareerPilot AI")
    st.caption("An AI career agent: it reads your profile, finds and ranks jobs, and shows what to learn next.")
    if notice := st.session_state.pop("notice", None):
        st.warning(notice)

    login_tab, register_tab = st.tabs(["Log in", "Create account"])
    with login_tab:
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", type="primary")
        if submitted:
            do_login(email, password)

    with register_tab:
        with st.form("register"):
            name = st.text_input("Full name")
            email = st.text_input("Email", key="reg_email")
            password = st.text_input("Password (8+ characters)", type="password", key="reg_pw")
            created = st.form_submit_button("Create account", type="primary")
        if created:
            try:
                with st.spinner("Creating your account..."):
                    wake_server()
                    request("POST", "/api/auth/register",
                            json={"email": email, "password": password, "full_name": name})
            except APIError as exc:
                st.error(str(exc))
            else:
                do_login(email, password)


# ---------- pages ----------
def profile_page() -> None:
    st.header("👤 Profile and resume")
    left, right = st.columns(2, gap="large")

    # The right column runs first, so the form on the left already shows the updated profile.
    with right:
        st.subheader("Upload your resume")
        file = st.file_uploader("Text-based PDF, up to 5 MB", type=["pdf"])
        if file is not None and st.button("Analyse resume", type="primary"):
            with st.spinner("Reading your resume..."):
                result = call("POST", "/api/resume/upload", timeout=120,
                              files={"file": (file.name, file.getvalue(), "application/pdf")})
            if result["resume"]["source"] == "gemini":
                st.success("Resume analysed with AI. Your profile was updated.")
            else:
                st.info("The AI was unavailable, so skills came from keyword matching. Your profile was updated.")

        try:
            latest = call("GET", "/api/resume/latest")
        except APIError as exc:
            if exc.status != 404:
                raise
            latest = None
        if latest:
            parsed = latest["parsed"]
            st.caption(f"Latest: {latest['filename']} (parsed by {latest['source']})")
            if parsed["summary"]:
                st.write(parsed["summary"])
            for edu in parsed["education"]:
                st.write(f"🎓 {edu['degree']} {edu['institution']} {edu['year']}".strip())
            for exp in parsed["experience"]:
                st.write(f"💼 {exp['title']} at {exp['company']} ({exp['duration']})")
            if parsed["projects"]:
                with st.expander("Projects"):
                    for project in parsed["projects"]:
                        st.write(f"- {project}")

    profile = call("GET", "/api/users/me/profile")
    with left:
        st.subheader("Your details")
        options = ["", *LEVELS]
        current = profile["experience_level"] if profile["experience_level"] in options else ""
        with st.form("profile"):
            skills = st.text_area("Skills (comma separated)", ", ".join(profile["skills"]), height=120)
            roles = st.text_input("Target roles", ", ".join(profile["target_roles"]))
            places = st.text_input("Preferred locations", ", ".join(profile["preferred_locations"]))
            level = st.selectbox("Experience level", options, index=options.index(current))
            education = st.text_input("Education", profile["education"] or "")
            summary = st.text_area("Summary", profile["summary"] or "", height=80)
            saved = st.form_submit_button("Save profile", type="primary")
        if saved:
            call("PUT", "/api/users/me/profile", json={
                "skills": split_list(skills),
                "target_roles": split_list(roles),
                "preferred_locations": split_list(places),
                "experience_level": level or None,
                "education": education or None,
                "summary": summary or None,
            })
            st.success("Profile saved.")


def search_page() -> None:
    st.header("🔎 Search jobs")
    with st.form("search"):
        query = st.text_input("What are you looking for?", placeholder="e.g. build chatbots with LLMs and RAG")
        c1, c2, c3, c4 = st.columns(4)
        location = c1.text_input("City (remote jobs included)")
        work_mode = c2.selectbox("Work mode", ["any", "onsite", "hybrid", "remote"])
        level = c3.selectbox("Level", ["any", *LEVELS])
        mode = c4.selectbox("Search mode", ["hybrid", "semantic", "keyword"])
        go = st.form_submit_button("Search", type="primary")

    if go:
        if len(query.strip()) < 2:
            st.warning("Type at least 2 characters.")
            return
        body = {"query": query.strip(), "mode": mode, "limit": 10}
        if location.strip():
            body["location"] = location.strip()
        if work_mode != "any":
            body["work_mode"] = work_mode
        if level != "any":
            body["experience_level"] = level
        with st.spinner("Searching..."):
            st.session_state["search_hits"] = call("POST", "/api/jobs/search", json=body)

    hits = st.session_state.get("search_hits")
    if hits is None:
        return
    if not hits:
        st.info("No jobs found. Try different words or remove a filter.")
    for hit in hits:
        def details(hit=hit):
            with st.expander("Description and scores"):
                st.write(hit["job"]["description"])
                st.caption(f"semantic {hit['semantic_score']:.2f} · keyword {hit['keyword_score']:.2f}")

        job_card(hit["job"], hit["score"], details)


def recommendations_page() -> None:
    st.header("⭐ Recommended for you")
    c1, c2 = st.columns([2, 1])
    location = c1.text_input("City filter (optional)")
    limit = c2.slider("How many jobs", 3, 20, 8)
    if st.button("Find my best matches", type="primary"):
        params = {"limit": limit}
        if location.strip():
            params["location"] = location.strip()
        with st.spinner("Ranking jobs for your profile..."):
            recs = call("GET", "/api/recommendations", params=params)
            path = call("GET", "/api/recommendations/learning-path")
        st.session_state["recs"] = (recs, path)

    saved = st.session_state.get("recs")
    if not saved:
        st.caption("Tip: fill your profile (or upload a resume) first.")
        return
    recs, path = saved

    if path["skills"]:
        st.subheader("📚 What to learn next")
        frame = pd.DataFrame(path["skills"][:8]).set_index("skill")
        st.bar_chart(frame["jobs_needing_it"], horizontal=True)
        st.caption(f"Number of your top {path['based_on_jobs']} jobs that need each skill.")

    st.subheader("Your matches")
    for rec in recs:
        def details(rec=rec):
            with st.expander("Why this score?"):
                for reason in rec["reasons"]:
                    st.write(f"- {reason}")
                if rec["matched_skills"]:
                    st.write("✅ You have: " + ", ".join(rec["matched_skills"]))
                if rec["missing_skills"]:
                    st.write("📌 To learn: " + ", ".join(rec["missing_skills"]))
                st.dataframe(pd.DataFrame([rec["breakdown"]]), hide_index=True)

        job_card(rec["job"], rec["score"], details)


def chat_page() -> None:
    st.header("💬 AI career assistant")
    state = st.session_state
    state.setdefault("chat", [])
    state.setdefault("conversation_id", None)

    top1, top2 = st.columns([3, 1])
    with top1.expander("What I remember about you"):
        memories = call("GET", "/api/agent/memories")
        if not memories:
            st.caption("Nothing yet. Tell me your preferences, for example 'I only want hybrid roles'.")
        for memory in memories:
            row, button = st.columns([6, 1])
            row.write(f"- {memory['content']}")
            if button.button("🗑", key=f"del_{memory['id']}"):
                call("DELETE", f"/api/agent/memories/{memory['id']}")
                st.rerun()
    if top2.button("New chat"):
        state.chat, state.conversation_id = [], None
        st.rerun()

    if not state.chat:
        st.caption("Try: 'Find me backend jobs in Gurgaon', 'Which jobs fit me best?', 'What should I learn next?'")
    for message in state.chat:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("meta"):
                st.caption(message["meta"])

    if prompt := st.chat_input("Ask about jobs, skills or what to learn next"):
        state.chat.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    reply = call("POST", "/api/agent/chat", timeout=120,
                                 json={"message": prompt, "conversation_id": state.conversation_id})
                except APIError as exc:
                    state.chat.pop()  # the server did not save this turn
                    st.error(str(exc))
                    return
            state.conversation_id = reply["conversation_id"]
            tools = ", ".join(dict.fromkeys(c["name"] for c in reply["tool_calls"])) or "none"
            source = "✨ Gemini" if reply["source"] == "gemini" else "⚙️ Fallback (no LLM)"
            meta = f"{source} · {reply['latency_ms'] / 1000:.1f}s · tools: {tools}"
            st.markdown(reply["reply"])
            st.caption(meta)
        state.chat.append({"role": "assistant", "content": reply["reply"], "meta": meta})


def metrics_table(entry: dict, names: list[str]) -> pd.DataFrame:
    rows = [{"system": n, **entry[n]} for n in names if entry.get(n)]
    return pd.DataFrame(rows).set_index("system")


def evaluation_page() -> None:
    st.header("📊 Evaluation")
    agent_tab, retrieval_tab = st.tabs(["Agent (my chats)", "Retrieval and ranking"])

    with agent_tab:
        m = call("GET", "/api/evaluation/agent")
        if not m["replies"]:
            st.info("No chats yet. Talk to the assistant first, then come back.")
        else:
            c = st.columns(4)
            c[0].metric("Replies", m["replies"])
            c[1].metric("Fallback rate", pct(m["fallback_rate"]))
            c[2].metric("Tool-call success", pct(m["tool_call_success_rate"]))
            c[3].metric("p95 latency", "n/a" if m["latency_p95_ms"] is None else f"{m['latency_p95_ms'] / 1000:.1f}s")
            c = st.columns(3)
            c[0].metric("Citation grounding", pct(m["citation_grounding_rate"]))
            c[1].metric("Citation consistency", pct(m["citation_consistency_rate"]))
            c[2].metric("Avg tool calls / reply", m["avg_tool_calls_per_reply"] or 0)
            st.caption(
                "Grounding: cited jobs that a tool really returned in that turn. "
                "A proxy for faithfulness, not the full thing. " + m["cost_note"]
            )

    with retrieval_tab:
        try:
            report = call("GET", "/api/evaluation/retrieval")
        except APIError as exc:
            if exc.status != 404:
                raise
            st.info("No report on the server. Run `python run_evaluation.py` and commit data/evaluation_report.json.")
            return
        st.caption(f"{report['num_jobs']} jobs · {report['num_queries']} queries · generated {report['generated_at']}")
        systems = ["keyword", "semantic", "hybrid_default", "hybrid_tuned"]
        for split in ("dev", "test"):
            entry = report["retrieval"][split]
            st.subheader(f"{split.capitalize()} split ({entry['n']} queries)")
            st.dataframe(metrics_table(entry, systems), use_container_width=True)
        st.subheader("Weight tuning (dev, NDCG@10)")
        st.line_chart(pd.DataFrame(report["tuning"]["grid"]).set_index("w_sem"))
        p = report["personalisation"]
        st.subheader(f"Personalisation ({p['n']} profiles)")
        st.dataframe(metrics_table(p, ["hybrid_profile_query", "personalized_ranker"]), use_container_width=True)
        for note in report["notes"]:
            st.caption(f"• {note}")


# ---------- main ----------
def main() -> None:
    if not st.session_state.get("token"):
        auth_page()
        return

    pages = {
        "👤 Profile & resume": profile_page,
        "🔎 Search jobs": search_page,
        "⭐ Recommendations": recommendations_page,
        "💬 Assistant": chat_page,
        "📊 Evaluation": evaluation_page,
    }
    with st.sidebar:
        st.markdown(f"### 🧭 CareerPilot\nHi, **{st.session_state['name']}**")
        choice = st.radio("Go to", list(pages), label_visibility="collapsed")
        if st.button("Log out"):
            st.session_state.clear()
            st.rerun()
    try:
        pages[choice]()
    except APIError as exc:
        st.error(str(exc))


main()