---
title: "Why We Built a Legal AI That Says 'I Don't Know'"
author: "Juhi Nebhnani, Siddhi Maheshwari"
date: "2026-01-16"
tags: ["@100xEngineers", "#0to100xEngineer", "GenAI", "LegalTech", "FullStack"]
---

# Why We Built a Legal AI That Says "I Don't Know"

---

## TL;DR

A lawyer uploads 2000 pages of case files. Ten minutes later, the system has found where the opposing side misquoted the law, caught a witness contradicting himself, and flagged a document supposedly signed before it existed. Cost: $14.

---

## The Problem: Miss One Detail, Lose the Case

A lawyer sits down with a 2000-page case file. Scanned PDFs. Handwritten notes. Documents in three languages. A hearing in two weeks.

The job? Find the one sentence on page 1,847 where a witness contradicts what he said on page 234. Spot where the opposing petition quotes a law incorrectly. Notice that a document was supposedly signed before it was notarized.

Miss any of this, and you walk into court unprepared. The other side didn't miss it.

**The tools available today don't solve this.** Most AI tools summarize documents or answer questions—but they don't *verify*. They don't check if a citation is accurate. They don't cross-reference statements across 2000 pages to find contradictions.

That's the gap Jaanch.ai fills.

---

## The Solution: Verification, Not Just Search

**Jaanch.ai** — *Verify, don't trust.*

It reads every page of a case file and finds:

- **Misquoted laws** — "The petition says Section 65B allows X. The actual Act says Y."
- **Contradictions** — "The witness said one thing on page 234. On page 1,847, he said the opposite."
- **Timeline problems** — "This document was supposedly signed two days before it existed."
- **Entity tracking** — The same person appears with different names across documents. Jaanch.ai knows they're the same person.

Every finding links to the source document and page. If the system can't trace it back, it doesn't show it.

**The demo:**

Upload a 2000-page case. Ten minutes later:
- The opposing petition misquoted the law on page 234
- A key witness contradicted himself between two documents
- The timeline shows a document signed before it existed

Cost: $14.

---

## What Makes This Different

**1. Citation Verification**

Lawyers spend hours checking if quoted laws are accurate. Jaanch.ai does it in seconds.

*Example:* A petition claims "Section 65B(4) requires X." Jaanch.ai checks the actual Act and shows the real text, side by side.

**2. Contradiction Detection**

Witnesses contradict themselves. Jaanch.ai catches it.

*Example:* In an affidavit, a person said the meeting was on January 5th. In the deposition, he said January 7th.

**3. Entity Resolution**

The same person appears with different names across 2000 pages. Jaanch.ai connects them.

*Example:* "Sharma" = "R.K. Sharma" = "Mr. Sharma" = "the respondent" — all linked automatically.

**4. Timeline Anomalies**

Some things are impossible. Jaanch.ai finds them.

*Example:* A document signed on March 3rd, but the notary stamp is dated March 1st.

---

## The Hardest Problem: Indian Legal Documents

The biggest challenge wasn't building AI features—it was handling Indian legal documents.

**The reality:**
- Scanned PDFs with poor image quality
- Handwritten notes mixed with typed text
- Three languages on the same page (English, Hindi, regional languages)
- Old documents with faded text and stamps

Most OCR tools fail on this. They either can't read the text, or they read it incorrectly with high confidence—which is worse.

**What worked:** Using enterprise OCR for the primary text extraction, then running a secondary validation pass on low-confidence sections. The system flags pages it's unsure about instead of guessing.

**What's still hard:** Handwritten regional language text remains unreliable. This is a known limitation—Jaanch.ai flags these sections for manual review rather than making confident mistakes.

**The lesson:** Sometimes "I don't know" is better than a wrong answer with high confidence.

---

## The Cost Problem (And How Hybrid AI Solved It)

Early research showed that running premium AI models on every chunk of a 2000-page document would cost $100+ per case. No law firm would pay that.

**The solution:** Route different tasks to different AI models.

- **Bulk tasks** (reading, extracting names and dates) → cheaper models
- **Complex reasoning** (finding contradictions, verifying citations) → smarter models, but only when needed

Result: $14 per case. Same quality, 7x cheaper.

**The lesson:** The right tool for each job beats the best tool for every job.

---

## Three Surprising Lessons

**1. Multi-language is harder than it looks.**

A single page might have English headers, Hindi body text, and a Gujarati stamp. Most OCR tools treat each language separately. But legal documents mix them mid-sentence. Getting this right required multiple processing passes and language detection at the paragraph level—not the page level.

**2. Lawyers verify everything twice.**

The initial assumption was that automation would replace manual review. Wrong. Lawyers don't want to skip verification—they want better tools *for* verification. Human-in-the-loop isn't a limitation of the system. It's the product. Every AI finding goes to a verification queue before it can be exported.

**3. Speed isn't the selling point.**

Fast but wrong is worthless. Lawyers would rather wait 10 minutes for accurate results than get instant answers they can't trust. The system prioritizes confidence scores and source traceability over response time. When accuracy and speed conflict, accuracy wins.

---

## The Numbers

| What | Value |
|------|-------|
| **Cost per case** | $14 for a 2000-page matter |
| **Processing speed** | 100 pages in ~5 minutes |
| **Privacy** | Cases are isolated; data never mixes |

---

## Under the Hood

- **Frontend:** Next.js, React, Tailwind CSS
- **Backend:** FastAPI (Python), async job processing
- **Database:** Supabase
- **AI:** Hybrid architecture—different models for different tasks

---

## About

Built by Juhi Nebhnani and Siddhi Maheshwari as part of the 100xEngineers program.

---

*What if you could walk into court knowing you've found every gap in the other side's story?*

*That's Jaanch.ai. Verify, don't trust.*

---

*Tags: @100xEngineers #0to100xEngineer #GenAI #LegalTech #FullStack*
