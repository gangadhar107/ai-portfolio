**AI Portfolio**

**v1.2 Feature Documentation**

What we are shipping, why it matters, and how we are building it

Gangadhar Allam | March 2026

# **1\. Why v1.2 Exists**

Version 1.1 shipped the Portfolio Intelligence layer. It works. Groq reads application and visit data from PostgreSQL and generates categorised insights. But testing it with real data revealed a fundamental problem: the LLM produced two wrong insights out of five because the context it received was incomplete.

The LLM flagged a ref code appearing multiple times as overreliance on a single source. It was actually one recruiter visiting multiple times. The LLM reasoned correctly on the data it saw. The data was just missing the metadata needed to interpret that pattern correctly.

This is not a prompt engineering problem. This is a context quality problem. v1.2 exists to fix the root cause, not the symptom.

**Core principle of v1.2**

The LLM is only as accurate as the context it receives. Every feature in this release either adds richer context to the database, improves how visits are tracked, or builds the infrastructure needed to sustain this system as data grows.

v1.2 ships five interconnected improvements:

- Richer application data through new columns in the applications table
- Smarter visit tracking through new columns in the visits table
- Traffic source tracking using UTM parameters and Google Analytics 4
- Internal visit exclusion so your own visits never corrupt the data
- Database migration from Neon to CockroachDB for more storage headroom

# **2\. Feature 1: Richer Application Data**

## **2.1 The Problem**

The current applications table stores company name, position, date applied, outcome, ref code and notes. That is enough to track that an application exists. It is not enough to understand why applications succeed or fail.

The LLM currently cannot answer these questions because the data does not exist:

- Did cold emails to founders perform better than portal applications?
- Do applications where you followed up convert at a higher rate?
- Which role category is converting best for your profile?
- How long does it typically take to hear back after applying?

## **2.2 The Solution: New Columns**

Add the following columns to the applications table. Each column is justified below.

| **Column**         | **Type** | **Values**                                                               | **Why it matters**                                                                                       |
| ------------------ | -------- | ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| outreach_channel   | ENUM     | cold_founder_email, hr_email, linkedin_dm, portal_apply, referral        | Most important missing field. Tells the LLM how you reached out so it can compare channel effectiveness. |
| contact_person     | ENUM     | founder, hr, hiring_manager, unknown                                     | Combined with outcome this shows whether the seniority of your contact affects conversion rate.          |
| role_category      | ENUM     | data_analyst, apm, founders_office, ai_engineer, business_analyst, other | Enables clean comparison across role types. Free text position field cannot be grouped reliably.         |
| followed_up        | BOOLEAN  | true or false                                                            | Distinguishes silence after application from a deliberate no-follow-up decision.                         |
| follow_up_date     | DATE     | date of first follow-up                                                  | Enables time-to-follow-up analysis. Do earlier follow-ups convert better?                                |
| follow_up_response | ENUM     | no_response, positive, negative, interview_scheduled                     | Tracks the outcome of the follow-up specifically, separate from the application outcome.                 |
| outcome_date       | DATE     | when outcome changed from pending                                        | Enables time-from-application-to-outcome analysis. How long does it take to hear back?                   |
| rejection_reason   | TEXT     | optional free text                                                       | Captures known rejection signals. Thin data now but valuable over time.                                  |

## **2.3 SQL Migration**

Run these statements on the database after migrating to CockroachDB:

ALTER TABLE applications ADD COLUMN outreach_channel TEXT;

ALTER TABLE applications ADD COLUMN contact_person TEXT;

ALTER TABLE applications ADD COLUMN role_category TEXT;

ALTER TABLE applications ADD COLUMN followed_up BOOLEAN DEFAULT FALSE;

ALTER TABLE applications ADD COLUMN follow_up_date DATE;

ALTER TABLE applications ADD COLUMN follow_up_response TEXT;

ALTER TABLE applications ADD COLUMN outcome_date DATE;

ALTER TABLE applications ADD COLUMN rejection_reason TEXT;

## **2.4 What This Unlocks for the LLM**

With these columns populated the LLM can generate insights that are currently impossible:

- Cold emails to founders have a 40% view rate but portal applications have 5%. Stop using portals for roles you genuinely want.
- Applications where you followed up within 7 days converted at 3x the rate of those where you did not follow up.
- APM roles are converting at 15% but Data Analyst roles at 2%. Your profile resonates more with product roles.
- HR contacts respond slower than founder contacts but convert at similar rates once they view the portfolio.

# **3\. Feature 2: Smarter Visit Tracking**

## **3.1 The Problem**

The current visits table stores ref code, timestamp, visit count, pages visited and country. This is enough to know that someone visited. It is not enough to understand the quality of that visit or distinguish between different visit patterns.

The specific bug from v1.1 testing was that multiple visits from one recruiter looked identical to multiple people sharing a ref code. The system had no way to tell the difference.

## **3.2 New Columns for the Visits Table**

| **Column**      | **Type** | **Example values**                     | **Why it matters**                                                                                                       |
| --------------- | -------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| is_return_visit | BOOLEAN  | true or false                          | Directly fixes the v1.1 bug. The LLM now knows repeat visits from one person are a positive signal, not a sourcing risk. |
| visit_source    | ENUM     | email_click, direct, linkedin, unknown | Tells you if your email subject line is working or if the recruiter found you another way.                               |
| time_on_site    | INTEGER  | seconds spent on portfolio             | High time on site signals genuine interest. Under 10 seconds is likely an accidental click.                              |
| utm_source      | TEXT     | linkedin, naukri, wellfound, resume    | Which platform sent this visitor. Required for traffic source analysis.                                                  |
| utm_medium      | TEXT     | profile, pdf, dm, cold_email           | How they arrived. Combined with utm_source tells you which combination works best.                                       |

## **3.3 How is_return_visit Is Detected**

When a visit is logged the system checks whether a previous visit exists for the same ref code. If yes the new visit is marked as a return visit. The logic in tracking.py becomes:

existing = check_previous_visit(ref_code)

is_return = True if existing else False

log_visit(ref_code, is_return_visit=is_return, ...)

**Why this matters**

With is_return_visit in place the LLM can say: this recruiter visited 3 times over 4 days, which is a high intent signal. Without it the LLM sees 3 visits and flags it as suspicious overreliance on a single ref code. Same data, completely different interpretation.

# **4\. Feature 3: Traffic Source Tracking with UTM Parameters**

## **4.1 The Problem**

The portfolio URL is shared across LinkedIn, Naukri, Wellfound, and resume PDFs. When a recruiter visits through any of these they arrive with no ref code. The current system logs them as an unknown visit or ignores them entirely. There is no way to know which platform is sending the most engaged visitors.

The workaround currently in use is creating an application entry with company name set to the platform name. This pollutes the applications table with non-application entries and makes LLM insights less accurate.

## **4.2 The Solution: Tagged URLs**

Each platform gets a unique URL with UTM parameters appended. When a visitor arrives through any of these links the visit logger reads the parameters and stores them in the visits table.

LinkedIn profile:

<https://ai-portfolio-three-green.vercel.app?utm_source=linkedin&utm_medium=profile>

Naukri profile:

<https://ai-portfolio-three-green.vercel.app?utm_source=naukri&utm_medium=profile>

Wellfound profile:

<https://ai-portfolio-three-green.vercel.app?utm_source=wellfound&utm_medium=profile>

Resume PDF:

<https://ai-portfolio-three-green.vercel.app?utm_source=resume&utm_medium=pdf>

## **4.3 Google Analytics 4 Integration**

Google Analytics 4 is added to the portfolio for anonymous traffic analysis. It reads UTM parameters automatically and tracks session behaviour across all pages. It handles things the custom system cannot: bounce rate, time on each page, device type, city-level geography, and organic search traffic.

For ref code visits the backend fires a custom GA4 event at the same time it writes to PostgreSQL. This event carries the company name, position and ref code so GA4 can show recruiter-level detail alongside anonymous traffic in one unified dashboard.

\# In log_visit() after writing to PostgreSQL

requests.post(GA4_ENDPOINT, json={

"client_id": ref_code,

"events": \[{

"name": "recruiter_visit",

"params": {

"ref_code": ref_code,

"company": application\["company_name"\],

"position": application\["position"\]

}

}\]

})

## **4.4 The Clean Boundary Between Systems**

Both systems serve different questions and do not overlap:

| **System**                    | **Answers**                                                                                                      | **Cannot answer**                                                             |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| PostgreSQL + custom dashboard | Who specifically visited? Which company? Which application? Did they visit again?                                | Where did anonymous visitors come from? What platform sends the most traffic? |
| Google Analytics 4            | How many people visited from LinkedIn? Which page has the highest bounce rate? What city are most visitors from? | Which specific recruiter visited? Which application did they click?           |

# **5\. Feature 4: Internal Visit Exclusion**

## **5.1 The Problem**

Every time you open the portfolio to test a feature, check how the dashboard looks, or review the insights page, that visit gets logged. It inflates visit counts and corrupts the LLM context. The AI starts reasoning about your own behaviour as if it were a recruiter.

This is a known problem in analytics. Apple's support teams faced the same issue when reviewing support pages. Internal visits must be separated from real user visits before any analysis can be trusted.

## **5.2 Two-Layer Exclusion**

**Layer 1: IP-based exclusion**

Your home or office IP address is stored as an environment variable. The visit logger checks every incoming request against this list before writing to the database. If the IP matches, the visit is skipped entirely.

EXCLUDED_IPS=192.168.1.100,103.21.45.67

def log_visit(ref_code, ip_address, ...):

excluded = os.getenv('EXCLUDED_IPS', '').split(',')

if ip_address in excluded:

return # skip logging

**Layer 2: Cookie-based exclusion**

When you log into the admin panel a cookie called portfolio_owner is set in your browser. The visit logger checks for this cookie and skips logging if it is present. This covers situations where your IP changes such as working from a cafe or using a VPN.

\# Set on admin login

response.set_cookie("portfolio_owner", "true", httponly=True)

\# Check in visit logger

if request.cookies.get("portfolio_owner") == "true":

return # skip logging

**Why both layers are needed**

IP exclusion handles most cases but your IP changes when you work from different locations. Cookie exclusion handles edge cases. Using both together is the standard approach used by professional analytics teams.

## **5.3 GA4 Internal Exclusion**

Google Analytics 4 has built-in support for internal traffic exclusion. Two steps are needed:

- Install the Google Analytics Opt-Out browser extension on every browser you use. This is the simplest and most reliable method.
- Create an IP filter in the GA4 admin panel under Data Streams. Add your known IP addresses there. GA4 will automatically exclude sessions from those IPs.

# **6\. Feature 5: Database Migration to CockroachDB**

## **6.1 Why Migrate Now**

Neon free tier offers 512MB of storage. The current database is under 400MB but v1.2 adds 8 new columns to the applications table and 5 new columns to the visits table. As outreach scales and more data is logged the buffer will shrink quickly.

Migrating now while the dataset is small is significantly easier than migrating later. The pain of database migration scales directly with data volume. A migration today with a few hundred rows takes minutes. The same migration with tens of thousands of rows takes hours and carries more risk.

**Why CockroachDB specifically**

CockroachDB Serverless offers 10GB on the free tier, which is 20 times more than Neon. It is PostgreSQL compatible which means zero code changes are needed. Only the connection string changes. The psycopg2 adapter, all raw SQL queries, and all existing routes work without modification.

## **6.2 Migration Steps**

- Create a CockroachDB account at cockroachlabs.com and create a new Serverless cluster. Choose the region closest to your Vercel deployment.
- Export the current Neon database to a SQL file:

pg_dump \$DATABASE_URL --no-owner --no-acl --format=plain > portfolio_backup.sql

- Review portfolio_backup.sql for the outcome_type ENUM definition. CockroachDB supports ENUMs so this should import cleanly.
- Import to CockroachDB using the connection string provided in the CockroachDB dashboard:

cockroach sql --url YOUR_COCKROACHDB_URL < portfolio_backup.sql

- Update the local .env file with the new connection string:

DATABASE_URL=postgresql://user:pass@host.cockroachlabs.com:26257/portfolio_db?sslmode=verify-full

- Note: CockroachDB uses port 26257 instead of PostgreSQL default 5432. Include this in the connection string.
- Test every route locally using uvicorn before pushing to Vercel. Check admin form, dashboard, visit logging, and insights generation.
- Update the DATABASE_URL environment variable in the Vercel dashboard.
- Push to GitHub and verify the live deployment works end to end.
- Run the ALTER TABLE statements from Section 2.3 to add the v1.2 columns.

## **6.3 Post-Migration Verification Checklist**

| **Test**                                | **Expected**                                 | **Status** |
| --------------------------------------- | -------------------------------------------- | ---------- |
| Admin form submits a new application    | Row appears in applications table            |            |
| Ref code link logs a visit              | Row appears in visits table                  |            |
| Dashboard loads with correct stats      | All stat cards show correct numbers          |            |
| AI Insights generates correctly         | Groq returns insights without error          |            |
| Outcome update saves correctly          | Outcome changes in applications table        |            |
| Email notification fires on first visit | Email received on test ref code click        |            |
| New v1.2 columns exist in table         | All 8 columns visible in schema              |            |
| Internal visit is excluded              | Own IP visit does not appear in visits table |            |

# **7\. Admin Form Updates**

## **7.1 What Needs to Change**

The admin form at /admin is where applications are entered manually. It currently captures company name, person name, position, date applied, and notes. The new columns from Section 2 require new form fields so the data actually gets populated.

Without updating the admin form the new columns will always be empty and the LLM will not benefit from the richer context.

## **7.2 New Fields to Add to the Admin Form**

| **Field label**    | **Input type** | **Options or format**                                                    |
| ------------------ | -------------- | ------------------------------------------------------------------------ |
| Outreach channel   | Dropdown       | Cold founder email, HR email, LinkedIn DM, Portal application, Referral  |
| Contact type       | Dropdown       | Founder, HR, Hiring manager, Unknown                                     |
| Role category      | Dropdown       | Data Analyst, APM, Founders Office, AI Engineer, Business Analyst, Other |
| Followed up        | Checkbox       | Checked or unchecked                                                     |
| Follow-up date     | Date picker    | Appears only when followed up is checked                                 |
| Follow-up response | Dropdown       | No response, Positive, Negative, Interview scheduled                     |

## **7.3 Backfilling Existing Applications**

The 40+ applications already in the database will have empty values for the new columns. You have two options:

- Backfill manually: Go through each existing application in the admin panel and fill in the new fields one by one. Time consuming but gives the LLM accurate historical context.
- Leave as null and start fresh: Existing applications will have null values for new columns. The LLM will ignore nulls and work with available data. New applications added after v1.2 will have complete data. Over time the dataset becomes more complete naturally.

The recommended approach is to backfill the outreach_channel and role_category fields for existing applications since these are the highest value columns for the LLM. Skip the rest for now.

# **8\. Implementation Order**

## **8.1 Why Order Matters**

These five features are interconnected. The database migration must happen before new columns are added. New columns must exist before the admin form can save them. UTM tracking must be set up before GA4 can receive data. Internal exclusion should be set up before any new data is collected.

Build in this order to avoid rework:

| **Step** | **Task**                                                              | **Files affected**                        | **Dependency**         |
| -------- | --------------------------------------------------------------------- | ----------------------------------------- | ---------------------- |
| 1        | Migrate database from Neon to CockroachDB                             | Environment variables only                | None. Do this first.   |
| 2        | Run ALTER TABLE for new columns                                       | Database schema only                      | Step 1 complete        |
| 3        | Set up internal visit exclusion                                       | routers/tracking.py, .env                 | Step 1 complete        |
| 4        | Add is_return_visit detection to visit logger                         | routers/tracking.py                       | Step 2 complete        |
| 5        | Update admin form with new fields                                     | templates/admin.html, routers/tracking.py | Step 2 complete        |
| 6        | Add UTM parameter reading to visit logger                             | routers/tracking.py                       | Step 2 complete        |
| 7        | Install GA4 on portfolio and configure exclusion                      | templates/base.html, GA4 dashboard        | Step 6 complete        |
| 8        | Add GA4 custom event for ref code visits                              | routers/tracking.py                       | Step 7 complete        |
| 9        | Update collect_portfolio_data() to include new columns                | routers/intelligence.py                   | Steps 2 and 5 complete |
| 10       | Update Groq system prompt to reference new context fields             | routers/intelligence.py                   | Step 9 complete        |
| 11       | Backfill outreach_channel and role_category for existing applications | Database directly or admin form           | Step 5 complete        |
| 12       | Full end to end test on live Vercel deployment                        | All routes                                | All steps complete     |

# **9\. What v1.2 Unlocks**

## **9.1 LLM Insights Before and After**

The difference in insight quality between v1.1 and v1.2 is significant. Here are concrete before and after examples:

| **v1.1 insight (incomplete context)**                         | **v1.2 insight (complete context)**                                                                                                               |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Low conversion rate. Review your application materials.       | Cold emails to founders have a 40% view rate. Portal applications have 5%. Your email works. Stop using portals.                                  |
| Lack of follow-up may be contributing to low conversion rate. | Applications where you followed up within 7 days converted at 3x the rate of those where you did not. Follow-up within a week.                    |
| Overreliance on single referral code detected.                | This ref code has 3 visits over 4 days from the same session. High intent signal. Follow up with this company today.                              |
| Most applications submitted in a short period.                | 20 applications were sent in a bulk outreach session on March 18 to 20. This is a deliberate strategy, not inconsistent effort. No action needed. |

## **9.2 New Questions the Dashboard Can Answer**

- Which outreach channel has the highest view rate: cold founder email, HR email, LinkedIn DM, or portal?
- Do applications where I followed up convert more than those where I did not?
- Which role category is converting best for my profile right now?
- How many anonymous visitors came from LinkedIn versus Naukri this week?
- Which page of my portfolio do recruiters spend the most time on?
- Are repeat visits from the same recruiter a reliable signal for getting a call?

## **9.3 The Story This Tells**

v1.2 is not just a technical improvement. It makes the portfolio system genuinely useful as a job search intelligence tool. Right now it tracks that people viewed your portfolio. After v1.2 it tells you exactly why your job search is or is not working and what to change.

That story, explained concisely, is also a strong talking point in interviews for PM and analytics roles. You built a system, tested it with real data, found where it failed, diagnosed the root cause, and shipped a structured fix. That is a complete product thinking loop.

# **10\. Commit Plan**

Each feature should be committed separately so the git history is clean and each change can be rolled back independently if needed.

| **Commit message**                                       | **What it covers**                                                          |
| -------------------------------------------------------- | --------------------------------------------------------------------------- |
| chore: migrate database from Neon to CockroachDB         | Connection string update, verification that all routes work on new database |
| feat: add v1.2 columns to applications and visits tables | All ALTER TABLE statements, schema changes                                  |
| feat: internal visit exclusion via IP and cookie check   | IP exclusion list, owner cookie logic in tracking.py                        |
| feat: return visit detection in visit logger             | is_return_visit logic in tracking.py                                        |
| feat: UTM parameter capture in visit logger              | utm_source and utm_medium reading and storage                               |
| feat: update admin form with v1.2 fields                 | New dropdowns and fields in admin.html, save_application() update           |
| feat: Google Analytics 4 integration with custom event   | GA4 script in base.html, custom event in tracking.py                        |
| feat: update Portfolio Intelligence for richer context   | collect_portfolio_data() update, Groq prompt update                         |
| docs: update CLAUDE.md for v1.2 completion               | Current task context updated, next feature noted                            |

_Prepared by Gangadhar Allam | March 2026 | AI Portfolio v1.2 Pre-Build Documentation_