const {
    Document, Packer, Paragraph, TextRun, HeadingLevel,
    AlignmentType, BorderStyle, LevelFormat
} = require('docx');
const fs = require('fs');

const BLUE = "1E3A5F";
const ACCENT = "2E86AB";
const GREEN = "1A7A4A";
const ORANGE = "C75000";
const RED = "AA0000";
const MUTED = "666666";

function h1(text) {
    return new Paragraph({
        heading: HeadingLevel.HEADING_1,
        spacing: { before: 400, after: 160 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: ACCENT, space: 6 } },
        children: [new TextRun({ text, bold: true, size: 36, color: BLUE, font: "Arial" })]
    });
}

function h2(text) {
    return new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 280, after: 100 },
        children: [new TextRun({ text, bold: true, size: 28, color: ACCENT, font: "Arial" })]
    });
}

function h3(text) {
    return new Paragraph({
        heading: HeadingLevel.HEADING_3,
        spacing: { before: 200, after: 80 },
        children: [new TextRun({ text, bold: true, size: 24, color: BLUE, font: "Arial" })]
    });
}

function para(text) {
    return new Paragraph({
        spacing: { before: 80, after: 80 },
        children: [new TextRun({ text, size: 22, font: "Arial" })]
    });
}

function bullet(text) {
    return new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        spacing: { before: 50, after: 50 },
        children: [new TextRun({ text, size: 22, font: "Arial" })]
    });
}

function task(status, text) {
    const colors = { done: GREEN, todo: BLUE, skip: RED };
    const labels = { done: "DONE", todo: "TODO", skip: "SKIP" };
    return new Paragraph({
        spacing: { before: 60, after: 60 },
        indent: { left: 360 },
        children: [
            new TextRun({ text: `[${labels[status]}] `, bold: true, size: 20, font: "Courier New", color: colors[status] }),
            new TextRun({ text, size: 22, font: "Arial" })
        ]
    });
}

function milestone(text) {
    return new Paragraph({
        spacing: { before: 160, after: 160 },
        indent: { left: 360 },
        border: { left: { style: BorderStyle.THICK, size: 6, color: GREEN, space: 8 } },
        children: [
            new TextRun({ text: "Milestone: ", bold: true, size: 22, font: "Arial", color: GREEN }),
            new TextRun({ text, size: 22, font: "Arial", italics: true })
        ]
    });
}

function note(text) {
    return new Paragraph({
        spacing: { before: 120, after: 120 },
        indent: { left: 360 },
        border: { left: { style: BorderStyle.THICK, size: 6, color: ORANGE, space: 8 } },
        children: [
            new TextRun({ text: "Note: ", bold: true, size: 22, font: "Arial", color: ORANGE }),
            new TextRun({ text, size: 22, font: "Arial" })
        ]
    });
}

function versionBox(version, title, desc, color) {
    return new Paragraph({
        spacing: { before: 120, after: 120 },
        indent: { left: 360 },
        border: { left: { style: BorderStyle.THICK, size: 8, color, space: 8 } },
        children: [
            new TextRun({ text: `${version} — `, bold: true, size: 24, font: "Arial", color }),
            new TextRun({ text: `${title}: `, bold: true, size: 24, font: "Arial" }),
            new TextRun({ text: desc, size: 22, font: "Arial", color: MUTED })
        ]
    });
}

function stackRow(label, value) {
    return new Paragraph({
        spacing: { before: 60, after: 60 },
        children: [
            new TextRun({ text: `${label}: `, bold: true, size: 22, font: "Arial", color: BLUE }),
            new TextRun({ text: value, size: 22, font: "Arial" })
        ]
    });
}

function spacer() {
    return new Paragraph({ spacing: { before: 60, after: 60 }, children: [new TextRun("")] });
}

function divider() {
    return new Paragraph({
        spacing: { before: 200, after: 200 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 2, color: "DDDDDD", space: 4 } },
        children: [new TextRun("")]
    });
}

const doc = new Document({
    numbering: {
        config: [
            {
                reference: "bullets",
                levels: [{
                    level: 0, format: LevelFormat.BULLET, text: "-",
                    alignment: AlignmentType.LEFT,
                    style: { paragraph: { indent: { left: 720, hanging: 360 } } }
                }]
            },
            {
                reference: "numbers",
                levels: [{
                    level: 0, format: LevelFormat.DECIMAL, text: "%1.",
                    alignment: AlignmentType.LEFT,
                    style: { paragraph: { indent: { left: 720, hanging: 360 } } }
                }]
            }
        ]
    },
    styles: {
        default: { document: { run: { font: "Arial", size: 22 } } },
        paragraphStyles: [
            {
                id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
                run: { size: 36, bold: true, font: "Arial", color: BLUE },
                paragraph: { spacing: { before: 400, after: 160 }, outlineLevel: 0 }
            },
            {
                id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
                run: { size: 28, bold: true, font: "Arial", color: ACCENT },
                paragraph: { spacing: { before: 280, after: 100 }, outlineLevel: 1 }
            },
            {
                id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
                run: { size: 24, bold: true, font: "Arial", color: BLUE },
                paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 }
            }
        ]
    },
    sections: [{
        properties: {
            page: {
                size: { width: 12240, height: 15840 },
                margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
            }
        },
        children: [

            // ─── TITLE ───
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { before: 1440, after: 200 },
                children: [new TextRun({ text: "AI-Powered Portfolio", bold: true, size: 60, font: "Arial", color: BLUE })]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { before: 0, after: 160 },
                children: [new TextRun({ text: "Updated Implementation Plan", bold: true, size: 40, font: "Arial", color: ACCENT })]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { before: 0, after: 80 },
                children: [new TextRun({ text: "Including tasks, stack decisions, and version roadmap", size: 24, font: "Arial", italics: true, color: MUTED })]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { before: 160, after: 80 },
                children: [new TextRun({ text: "Version 1.0  |  Python + FastAPI + PostgreSQL  |  $0/month", bold: true, size: 24, font: "Arial", color: GREEN })]
            }),
            spacer(),

            // ─── VERSION ROADMAP ───
            h1("Version Roadmap"),
            para("Three versions. Each builds on a proven, working foundation. No skipping ahead."),
            spacer(),
            versionBox("v1.0", "Ship Now", "Portfolio website + ref code tracking + private dashboard + SQL analytics. Zero AI. Get live and start applying.", GREEN),
            versionBox("v2.0", "RAG Chatbot", "Single agent chatbot powered by Groq free tier. Knows your work. Answers visitor questions. Add after you have real application data.", ACCENT),
            versionBox("v3.0", "Multi-Agent", "PM routing agent + specialist agents using Claude Code subagents. Add after v2.0 is stable and you have a job or strong traction.", ORANGE),
            spacer(),
            note("Your mentor's rule: build less, ship faster, measure everything, iterate with data. v1.0 gives you the measurement system. Everything else follows from real data."),
            spacer(),

            // ─── STACK ───
            h1("v1.0 Tech Stack"),
            para("Every decision here prioritizes simplicity, Python familiarity, and zero monthly cost."),
            spacer(),
            stackRow("Language", "Python"),
            stackRow("Framework", "FastAPI + Jinja2 templates"),
            stackRow("Database (dev)", "PostgreSQL — local on your machine"),
            stackRow("Database (prod)", "Neon free tier — swap one connection string in .env when deploying"),
            stackRow("ORM / DB adapter", "psycopg2-binary — direct PostgreSQL driver, no extra abstraction"),
            stackRow("Hosting", "Vercel free tier"),
            stackRow("Booking", "Calendly free tier"),
            stackRow("Security scan", "Snyk free tier — connected to GitHub"),
            stackRow("Version control", "GitHub — already set up"),
            stackRow("Notifications", "Python smtplib or Resend free tier"),
            stackRow("Charts", "Plotly — Python library, free"),
            spacer(),
            note("Supabase removed — API issues encountered. PostgreSQL directly with psycopg2 is simpler, more reliable, and gives you better SQL learning since you are closer to the raw database."),
            spacer(),

            // ─── ACCOUNTS ───
            h1("Accounts Needed Before Phase 3"),
            para("Create these as you reach each phase. Not all needed immediately."),
            spacer(),
            bullet("GitHub — already done"),
            bullet("Neon (neon.tech) — needed at Phase 6 deploy, free, no credit card"),
            bullet("Vercel (vercel.com) — needed at Phase 6 deploy, free"),
            bullet("Calendly (calendly.com) — needed at Phase 3 content, free"),
            bullet("Snyk (snyk.io) — needed at Phase 5 security, connect to GitHub, free"),
            spacer(),

            // ─── PHASE 0 ───
            h1("Phase 0 — Project Initialization"),
            para("Goal: Safe, clean project foundation before any real code. Status: COMPLETED."),
            spacer(),
            h3("Tasks"),
            task("done", "Create GitHub repository ai-portfolio"),
            task("done", "Create FastAPI project folder structure"),
            task("done", "Create .gitignore — .env, __pycache__, venv, chroma_db excluded"),
            task("done", "Create .env.example with placeholder variable names and comments"),
            task("done", "Set up Python virtual environment (venv)"),
            task("done", "Install dependencies from requirements.txt"),
            task("done", "Verify FastAPI dev server runs at http://127.0.0.1:8000"),
            task("done", "First git commit: Phase 0 project initialization"),
            spacer(),
            milestone("Clean repo on GitHub. .gitignore protecting all secrets. FastAPI running locally. Phase 0 complete."),
            spacer(),

            // ─── PHASE 1 ───
            h1("Phase 1 — Database Design"),
            para("Goal: Design and create the data layer in local PostgreSQL. Connect it to FastAPI. Status: IN PROGRESS."),
            spacer(),
            h3("Database — Three Tables"),
            spacer(),
            new Paragraph({ spacing: { before: 60, after: 40 }, children: [new TextRun({ text: "applications — stores every job application you submit", bold: true, size: 22, font: "Arial" })] }),
            bullet("id — SERIAL PRIMARY KEY"),
            bullet("company_name — TEXT NOT NULL"),
            bullet("person_name — TEXT (optional)"),
            bullet("position — TEXT NOT NULL"),
            bullet("date_applied — DATE NOT NULL"),
            bullet("outcome — ENUM: pending / got_call / rejected / no_response (default: pending)"),
            bullet("ref_code — TEXT UNIQUE — the opaque tracking code"),
            bullet("notes — TEXT (optional)"),
            bullet("created_at — TIMESTAMPTZ default NOW()"),
            spacer(),
            new Paragraph({ spacing: { before: 60, after: 40 }, children: [new TextRun({ text: "visits — logs every time a ref link is opened", bold: true, size: 22, font: "Arial" })] }),
            bullet("id — SERIAL PRIMARY KEY"),
            bullet("ref_code — TEXT NOT NULL"),
            bullet("timestamp — TIMESTAMPTZ default NOW()"),
            bullet("visit_count — INTEGER default 1"),
            bullet("pages_visited — TEXT (optional)"),
            bullet("country — TEXT (optional)"),
            spacer(),
            new Paragraph({ spacing: { before: 60, after: 40 }, children: [new TextRun({ text: "ref_codes — maps opaque codes to applications", bold: true, size: 22, font: "Arial" })] }),
            bullet("id — SERIAL PRIMARY KEY"),
            bullet("ref_code — TEXT UNIQUE NOT NULL"),
            bullet("application_id — INTEGER REFERENCES applications(id)"),
            bullet("created_date — TIMESTAMPTZ default NOW()"),
            bullet("is_active — BOOLEAN default TRUE"),
            spacer(),
            h3("Tasks"),
            task("done", "Install PostgreSQL locally"),
            task("done", "Create portfolio_db database and portfolio_user"),
            task("todo", "Run SQL to create all three tables with constraints"),
            task("todo", "Insert fake test data to verify tables work"),
            task("todo", "Run 4 verification queries — SELECT, JOIN, FILTER"),
            task("todo", "Update database/__init__.py with get_connection() and get_cursor()"),
            task("todo", "Update requirements.txt — replace supabase with psycopg2-binary"),
            task("todo", "Update .env.example — replace Supabase vars with DATABASE_URL"),
            task("todo", "Update real .env with local DATABASE_URL"),
            task("todo", "Write and run test_connection.py to verify Python connects to PostgreSQL"),
            task("todo", "Delete fake test data after verification"),
            task("todo", "Delete test_connection.py"),
            task("todo", "Git commit: Phase 1 PostgreSQL database setup and connection"),
            spacer(),
            milestone("Three tables in local PostgreSQL. Python connected via psycopg2. Verified with real queries. Phase 1 complete."),
            spacer(),

            // ─── PHASE 2 ───
            h1("Phase 2 — Ref Code Tracking System"),
            para("Goal: Generate unique opaque ref codes and silently log every portfolio visit. Your most original feature."),
            spacer(),
            h3("Features to Build"),
            bullet("Ref code generator — Python secrets module, 8-character alphanumeric, guaranteed unique"),
            bullet("Private application form — password protected, only you access it"),
            bullet("Visit logger — silently captures ?ref= param on every portfolio visit"),
            bullet("Real-time email notification — fires on first visit to each ref link"),
            bullet("Private dashboard — table of all applications with visit and outcome data"),
            spacer(),
            h3("Routes to Create"),
            bullet("POST /generate-ref — generates ref code, saves to database, returns full URL"),
            bullet("GET /admin — private application form (password protected)"),
            bullet("POST /admin/application — saves new application and generates ref code"),
            bullet("GET / — home page, triggers visit logger if ?ref= present in URL"),
            bullet("GET /dashboard — private dashboard (password protected)"),
            bullet("POST /dashboard/update-outcome — updates application outcome manually"),
            spacer(),
            h3("Tasks"),
            task("todo", "Write generate_ref_code() function in routers/tracking.py using secrets module"),
            task("todo", "Write save_application() function that inserts to applications and ref_codes tables"),
            task("todo", "Write log_visit() function that inserts to visits table"),
            task("todo", "Build /admin route with password check middleware"),
            task("todo", "Build application form HTML template (templates/admin.html)"),
            task("todo", "Wire POST /admin/application to save_application() and return generated link"),
            task("todo", "Add visit logger to GET / route — checks for ?ref= and calls log_visit()"),
            task("todo", "Set up email notification using smtplib — fires on first visit only"),
            task("todo", "Build /dashboard route with password check"),
            task("todo", "Build dashboard HTML template (templates/dashboard.html)"),
            task("todo", "Dashboard shows: company, position, date applied, viewed badge, view count, outcome dropdown"),
            task("todo", "Wire POST /dashboard/update-outcome to update applications table"),
            task("todo", "Test full flow: generate ref link, open it, verify dashboard logs it, verify email arrives"),
            task("todo", "Git commit: Phase 2 ref code tracking system"),
            spacer(),
            milestone("Generate a ref link. Open it in browser. See it logged in dashboard. Receive email notification. Full tracking loop working."),
            spacer(),

            // ─── PHASE 3 ───
            h1("Phase 3 — Portfolio Content & Structure"),
            para("Goal: Build the actual portfolio pages with real content. This must work without any AI. If it does not impress on its own, nothing else can save it."),
            spacer(),
            h3("Pages to Build"),
            bullet("Home — headline, subheading, two CTAs, currently open to work badge"),
            bullet("About — your story in three paragraphs, honest and human"),
            bullet("Projects — documented cards using the consistent structure below"),
            bullet("Blog — learning journal entries listed newest first"),
            bullet("Contact — Calendly embed for 30-minute session booking"),
            spacer(),
            h3("Project Card Structure (use for every project)"),
            bullet("Project name and one-line description"),
            bullet("The problem — what does this solve and why does it matter"),
            bullet("Your approach — decisions made and why"),
            bullet("What you built — explained simply"),
            bullet("Tech used — stack with brief reason for each choice"),
            bullet("What you learned — honest including what went wrong"),
            bullet("GitHub link or live link"),
            spacer(),
            h3("UI Design Direction"),
            bullet("Inspired by PostHog.com — dark theme, bold typography, card borders, dense but readable"),
            bullet("Background: #0f0f0f, Text: #f5f0e8, Accent: #e8d44d"),
            bullet("Fonts: Inter for body, JetBrains Mono for code labels"),
            bullet("Cards: 1px visible border, subtle hover lift — no floating shadows"),
            bullet("Fully responsive — tested on mobile 320px minimum width"),
            spacer(),
            h3("Tasks"),
            task("todo", "Set up Calendly account and 30-minute meeting slot"),
            task("todo", "Create base.html Jinja2 template with dark theme, nav, footer"),
            task("todo", "Build home page — headline, subheading, CTAs, open to work badge"),
            task("todo", "Build about page — three honest paragraphs about your journey"),
            task("todo", "Write project descriptions for all current projects using consistent structure"),
            task("todo", "Build projects page with documented project cards"),
            task("todo", "Build blog page — learning journal listing newest first"),
            task("todo", "Write first blog post: Why I decided to build my own AI-powered portfolio"),
            task("todo", "Build contact page with Calendly embed"),
            task("todo", "Apply PostHog-inspired dark theme across all pages"),
            task("todo", "Test all pages on mobile and two browsers"),
            task("todo", "Verify: if chatbot disappeared tomorrow would this still impress a recruiter"),
            task("todo", "Git commit: Phase 3 portfolio content and UI"),
            spacer(),
            milestone("Portfolio has real content that stands on its own. All pages built and mobile responsive. First blog post written."),
            spacer(),

            // ─── PHASE 4 ───
            h1("Phase 4 — SQL Analytics Layer"),
            para("Goal: Extract real insights from your tracking data. This is what makes your story unique — most candidates have zero signal from their job search."),
            spacer(),
            h3("Insight Queries to Write"),
            bullet("All applications where portfolio was viewed at least once"),
            bullet("Applications viewed more than once — high intent companies"),
            bullet("Viewed but no call received — where are you losing people"),
            bullet("View to call conversion rate overall"),
            bullet("Conversion rate by position type"),
            bullet("Average time between application date and first view"),
            bullet("Weekly view trend over time"),
            spacer(),
            h3("Tasks"),
            task("todo", "Create /sql_queries folder in project root"),
            task("todo", "Write and save each insight query as a named .sql file with comment explaining what it answers"),
            task("todo", "Add plotly to requirements.txt"),
            task("todo", "Add four stat cards to private dashboard: Total Applied, Total Viewed, Total Calls, Conversion Rate"),
            task("todo", "Add bar chart to dashboard: applications sent vs viewed vs calls"),
            task("todo", "Add weekly view trend line chart to dashboard"),
            task("todo", "Write first data insights blog post after first 20 applications"),
            task("todo", "Git commit: Phase 4 SQL analytics layer"),
            spacer(),
            milestone("Dashboard shows real charts from real data. SQL query library documented. First data insights post written."),
            spacer(),

            // ─── PHASE 5 ───
            h1("Phase 5 — Security Audit"),
            para("Goal: Safe and production ready before anyone else can access it."),
            spacer(),
            h3("Tasks"),
            task("todo", "Connect Snyk to GitHub repository"),
            task("todo", "Run Snyk full scan — fix all high and critical issues"),
            task("todo", "Search entire codebase for hardcoded secrets — result must be zero"),
            task("todo", "Verify .env is in .gitignore and never appears in git history"),
            task("todo", "Test /dashboard and /admin routes without login — must be fully blocked"),
            task("todo", "Test visit logger with invalid or missing ref codes — must fail gracefully"),
            task("todo", "Test email notification with a real ref link"),
            task("todo", "Check all forms for basic input validation"),
            task("todo", "Git commit: Phase 5 security audit"),
            spacer(),
            milestone("Snyk clean. No secrets in codebase. All protected routes locked. All edge cases handled gracefully."),
            spacer(),

            // ─── PHASE 6 ───
            h1("Phase 6 — Deploy & Go Live"),
            para("Goal: Live URL you can put in every job application, email, and LinkedIn profile. Start applying the day this is done."),
            spacer(),
            h3("Database Migration — Local to Cloud"),
            para("This is the only infrastructure change at deploy time. Your code does not change — only the connection string."),
            bullet("Create a free account at neon.tech — no credit card required"),
            bullet("Create a new project called portfolio-db"),
            bullet("Run your Phase 1 CREATE TABLE SQL in the Neon SQL editor"),
            bullet("Copy the connection string Neon gives you"),
            bullet("Add it as DATABASE_URL in Vercel environment variables"),
            bullet("Your local .env keeps pointing to local PostgreSQL for development"),
            spacer(),
            h3("Tasks"),
            task("todo", "Create Neon account and portfolio-db project"),
            task("todo", "Run Phase 1 table creation SQL in Neon SQL editor"),
            task("todo", "Create Vercel account and connect GitHub repository"),
            task("todo", "Add all environment variables in Vercel dashboard: DATABASE_URL, DASHBOARD_PASSWORD, NOTIFICATION_EMAIL, NOTIFICATION_EMAIL_PASSWORD, BASE_URL, CALENDLY_LINK"),
            task("todo", "Deploy to Vercel"),
            task("todo", "Test full flow on live URL from a different device"),
            task("todo", "Generate first real ref code for a real job application"),
            task("todo", "Open the live ref link and verify dashboard logs it"),
            task("todo", "Verify email notification arrives"),
            task("todo", "Test chatbot questions and Calendly booking"),
            task("todo", "Optional: buy yourname.dev domain (~$10-15/year) and connect to Vercel"),
            task("todo", "Write launch blog post documenting the full journey"),
            task("todo", "Start applying — put the live URL in every application"),
            spacer(),
            milestone("Live URL. Full tracking loop working in production. Blog documents the journey. Actively applying with data."),
            spacer(),

            // ─── FEEDBACK LOOP ───
            h1("Your Job Search Feedback Loop"),
            para("Use this decision framework as you collect real application data:"),
            spacer(),
            new Paragraph({
                spacing: { before: 80, after: 60 },
                children: [
                    new TextRun({ text: "Viewed + got a call  ", bold: true, size: 22, font: "Arial", color: GREEN }),
                    new TextRun({ text: "Profile and presentation are working. Double down on this direction and type of role.", size: 22, font: "Arial" })
                ]
            }),
            new Paragraph({
                spacing: { before: 60, after: 60 },
                children: [
                    new TextRun({ text: "Viewed + no call  ", bold: true, size: 22, font: "Arial", color: ORANGE }),
                    new TextRun({ text: "They were interested enough to look but something did not convert. Review the project matching the role. Reorder your project cards.", size: 22, font: "Arial" })
                ]
            }),
            new Paragraph({
                spacing: { before: 60, after: 80 },
                children: [
                    new TextRun({ text: "Did not view  ", bold: true, size: 22, font: "Arial", color: RED }),
                    new TextRun({ text: "Problem is at the outreach stage, not the portfolio. Your resume or email subject line needs work.", size: 22, font: "Arial" })
                ]
            }),
            spacer(),
            note("Review your data after every 20 applications. Write down one thing you are changing and why. That iteration documented in your blog is more impressive than any technical feature."),
            spacer(),

            // ─── V2 AND V3 ───
            h1("Future Versions — Do Not Build These Now"),
            spacer(),
            h2("Version 2.0 — RAG Chatbot"),
            para("Build this after you have a job or after you have real portfolio traffic data showing visitors want to engage conversationally."),
            spacer(),
            bullet("Single agent RAG chatbot — no orchestration, no routing"),
            bullet("LLM: Groq free tier — LLaMA 3.3 70B or Mistral 7B"),
            bullet("Stack: LangChain + ChromaDB + Groq API"),
            bullet("Knowledge base: markdown files from your portfolio content"),
            bullet("Booking intent detection — surfaces Calendly link when visitor wants to connect"),
            bullet("Embedded as floating chat widget on portfolio"),
            spacer(),
            h2("Version 3.0 — Multi-Agent Layer"),
            para("Build this when you are applying for LLM infrastructure roles and can articulate the architectural tradeoffs deeply."),
            spacer(),
            bullet("PM routing agent — receives all questions, routes to right specialist"),
            bullet("Project explainer agent — handles project and tech questions"),
            bullet("AI engineer agent — handles chatbot and RAG architecture questions"),
            bullet("Booking agent — handles hiring and collaboration questions"),
            bullet("Built using Claude Code subagents defined as markdown files"),
            bullet("Document the architecture and tradeoffs as a project on your portfolio"),
            spacer(),

            // ─── TASK SUMMARY ───
            h1("Task Summary"),
            spacer(),
            new Paragraph({
                spacing: { before: 60, after: 60 },
                children: [
                    new TextRun({ text: "Phase 0 — Project Init:  ", bold: true, size: 22, font: "Arial", color: GREEN }),
                    new TextRun({ text: "8 tasks — NOT STARTED", size: 22, font: "Arial", color: BLUE })
                ]
            }),
            new Paragraph({
                spacing: { before: 60, after: 60 },
                children: [
                    new TextRun({ text: "Phase 1 — Database:  ", bold: true, size: 22, font: "Arial", color: ORANGE }),
                    new TextRun({ text: "13 tasks — NOT STARTED", size: 22, font: "Arial", color: BLUE })
                ]
            }),
            new Paragraph({
                spacing: { before: 60, after: 60 },
                children: [
                    new TextRun({ text: "Phase 2 — Tracking System:  ", bold: true, size: 22, font: "Arial", color: BLUE }),
                    new TextRun({ text: "14 tasks — NOT STARTED", size: 22, font: "Arial", color: BLUE })
                ]
            }),
            new Paragraph({
                spacing: { before: 60, after: 60 },
                children: [
                    new TextRun({ text: "Phase 3 — Portfolio Content:  ", bold: true, size: 22, font: "Arial", color: BLUE }),
                    new TextRun({ text: "13 tasks — NOT STARTED", size: 22, font: "Arial", color: BLUE })
                ]
            }),
            new Paragraph({
                spacing: { before: 60, after: 60 },
                children: [
                    new TextRun({ text: "Phase 4 — SQL Analytics:  ", bold: true, size: 22, font: "Arial", color: BLUE }),
                    new TextRun({ text: "8 tasks — NOT STARTED", size: 22, font: "Arial", color: BLUE })
                ]
            }),
            new Paragraph({
                spacing: { before: 60, after: 60 },
                children: [
                    new TextRun({ text: "Phase 5 — Security Audit:  ", bold: true, size: 22, font: "Arial", color: BLUE }),
                    new TextRun({ text: "8 tasks — NOT STARTED", size: 22, font: "Arial", color: BLUE })
                ]
            }),
            new Paragraph({
                spacing: { before: 60, after: 60 },
                children: [
                    new TextRun({ text: "Phase 6 — Deploy:  ", bold: true, size: 22, font: "Arial", color: BLUE }),
                    new TextRun({ text: "13 tasks — NOT STARTED", size: 22, font: "Arial", color: BLUE })
                ]
            }),
            spacer(),
            new Paragraph({
                spacing: { before: 80, after: 80 },
                children: [
                    new TextRun({ text: "Total v1.0 tasks: ", bold: true, size: 22, font: "Arial" }),
                    new TextRun({ text: "77 tasks across 6 phases", size: 22, font: "Arial" }),
                ]
            }),
            spacer(),

            // ─── CLOSING ───
            divider(),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { before: 200, after: 80 },
                children: [new TextRun({ text: "Build less. Ship faster. Measure everything. Iterate with data.", bold: true, size: 26, font: "Arial", color: BLUE, italics: true })]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                spacing: { before: 0, after: 80 },
                children: [new TextRun({ text: "That is the story that gets you hired.", size: 24, font: "Arial", color: MUTED, italics: true })]
            }),

        ]
    }]
});

Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync('/home/claude/AI_Portfolio_Implementation_Plan.docx', buffer);
    console.log('Done');
});