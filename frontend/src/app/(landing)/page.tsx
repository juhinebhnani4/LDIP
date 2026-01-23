import Image from "next/image"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import {
  Scale,
  FileSearch,
  Clock,
  Users,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ArrowRight,
} from "lucide-react"

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-sm border-b border-border">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <Image
              src="/logo-full.png"
              alt="jaanch.ai"
              width={120}
              height={32}
              className="h-8 w-auto"
              style={{ width: 'auto', height: 'auto' }}
            />
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/login">
              <Button variant="ghost" className="font-medium">
                Log in
              </Button>
            </Link>
            <Link href="/signup">
              <Button className="bg-primary text-primary-foreground hover:bg-primary/90">
                Get Started
              </Button>
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Left: Copy */}
            <div className="text-center lg:text-left">
              <h1 className="font-serif text-4xl md:text-5xl lg:text-6xl font-bold text-primary leading-tight mb-6">
                Lawyers miss what matters.
                <br />
                <span className="text-accent">We don&apos;t.</span>
              </h1>
              <p className="text-lg text-muted-foreground mb-3 font-medium">
                Verify, don&apos;t trust.
              </p>
              <p className="text-lg text-foreground/80 mb-8 leading-relaxed">
                jaanch.ai reads every page and finds what humans miss — contradictions,
                misquoted laws, timeline gaps. Every finding cited to the exact page.
              </p>
              <Link href="/signup">
                <Button
                  size="lg"
                  className="bg-primary text-primary-foreground hover:bg-primary/90 text-lg px-8 py-6 h-auto"
                >
                  See what you&apos;re missing
                  <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
              </Link>
            </div>

            {/* Right: Finding Card Mockup */}
            <div className="relative">
              {/* Background document stack effect */}
              <div className="absolute -top-4 -left-4 w-full h-full bg-muted/50 rounded-lg transform rotate-2" />
              <div className="absolute -top-2 -left-2 w-full h-full bg-muted/30 rounded-lg transform rotate-1" />

              {/* Main finding card */}
              <div className="relative bg-card border border-border rounded-lg shadow-lg overflow-hidden">
                {/* Card header */}
                <div className="bg-destructive/10 border-b border-destructive/20 px-4 py-3 flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-destructive animate-pulse" />
                  <span className="text-sm font-semibold text-destructive">Contradiction Found</span>
                </div>

                {/* Card content */}
                <div className="p-5 space-y-4">
                  {/* Statement A */}
                  <div className="bg-muted/50 rounded-md p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-mono bg-primary/10 text-primary px-2 py-0.5 rounded">
                        Affidavit_2019.pdf • Page 47
                      </span>
                    </div>
                    <p className="text-sm text-foreground">
                      &ldquo;The shares were transferred to the petitioner on{" "}
                      <span className="bg-accent/20 px-1 font-medium">15th March 2018</span>.&rdquo;
                    </p>
                  </div>

                  {/* Conflict indicator */}
                  <div className="flex items-center justify-center">
                    <div className="flex items-center gap-2 text-destructive">
                      <div className="h-px w-8 bg-destructive/30" />
                      <AlertTriangle className="h-4 w-4" />
                      <span className="text-xs font-semibold">CONFLICTS WITH</span>
                      <div className="h-px w-8 bg-destructive/30" />
                    </div>
                  </div>

                  {/* Statement B */}
                  <div className="bg-muted/50 rounded-md p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-mono bg-primary/10 text-primary px-2 py-0.5 rounded">
                        Company_Letter.pdf • Page 12
                      </span>
                    </div>
                    <p className="text-sm text-foreground">
                      &ldquo;No transfer occurred until{" "}
                      <span className="bg-accent/20 px-1 font-medium">22nd August 2019</span>.&rdquo;
                    </p>
                  </div>

                  {/* Confidence badge */}
                  <div className="flex items-center justify-between pt-2 border-t border-border">
                    <span className="text-xs text-muted-foreground">Confidence: 94%</span>
                    <button className="text-xs text-primary font-medium hover:underline">
                      View in documents →
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* The Problem Section */}
      <section className="py-20 px-6 bg-muted/30">
        <div className="max-w-5xl mx-auto">
          <div className="grid lg:grid-cols-5 gap-10 items-center">
            {/* Left: Document stack visual */}
            <div className="lg:col-span-2 flex justify-center">
              <div className="relative w-48 h-64">
                {/* Stacked documents */}
                {[...Array(5)].map((_, i) => (
                  <div
                    key={i}
                    className="absolute bg-card border border-border rounded shadow-sm"
                    style={{
                      width: "100%",
                      height: "100%",
                      transform: `rotate(${-8 + i * 4}deg) translateY(${i * -4}px)`,
                      zIndex: i,
                    }}
                  >
                    {/* Document lines */}
                    <div className="p-4 space-y-2">
                      <div className="h-2 bg-muted rounded w-3/4" />
                      <div className="h-2 bg-muted rounded w-full" />
                      <div className="h-2 bg-muted rounded w-5/6" />
                      <div className="h-2 bg-muted rounded w-2/3" />
                      {i === 4 && (
                        <>
                          <div className="h-2 bg-destructive/30 rounded w-full mt-4" />
                          <div className="h-2 bg-muted rounded w-4/5" />
                          <div className="h-2 bg-accent/30 rounded w-3/4" />
                        </>
                      )}
                    </div>
                  </div>
                ))}
                {/* Page count badge */}
                <div className="absolute -bottom-4 -right-4 bg-primary text-primary-foreground text-sm font-bold px-3 py-1 rounded-full shadow-lg z-10">
                  700+ pages
                </div>
              </div>
            </div>

            {/* Right: Copy */}
            <div className="lg:col-span-3">
              <h2 className="font-serif text-3xl md:text-4xl font-bold text-primary mb-6">
                Contradictions hiding
                <br />
                <span className="text-destructive">in plain sight.</span>
              </h2>
              <div className="space-y-4 text-foreground/80">
                <p>
                  A Special Court dispute over shares worth crores. 25 years of documents.
                  Affidavits, company letters, court orders.
                </p>
                <p>
                  Buried inside: contradictory ownership claims, meetings that violated
                  court provisions, transfers without notification.
                </p>
                <p className="font-medium text-foreground">
                  Multiple legal teams reviewed these files.
                  <span className="text-destructive"> Nobody caught them all.</span>
                </p>
              </div>
              <p className="text-lg font-serif font-semibold text-primary mt-6">
                That&apos;s the gap jaanch.ai fills.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* What jaanch Finds Section */}
      <section className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <h2 className="font-serif text-3xl md:text-4xl font-bold text-primary mb-4 text-center">
            What jaanch catches that humans miss
          </h2>
          <p className="text-center text-muted-foreground mb-12 text-lg">
            Four specialized engines working in parallel
          </p>

          <div className="grid md:grid-cols-2 gap-6">
            {/* Misquoted Laws */}
            <div className="bg-card border border-border rounded-lg p-6 shadow-sm">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-destructive/10 rounded-lg">
                  <Scale className="h-6 w-6 text-destructive" />
                </div>
                <h3 className="font-serif text-xl font-semibold text-primary">
                  Misquoted Laws
                </h3>
              </div>
              <p className="text-foreground/80 mb-4">
                &ldquo;The petition says Section 65B allows X. The actual Act says Y.&rdquo;
              </p>
              <p className="text-sm text-muted-foreground font-medium">
                Side-by-side comparison, instantly.
              </p>
            </div>

            {/* Contradictions */}
            <div className="bg-card border border-border rounded-lg p-6 shadow-sm">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-destructive/10 rounded-lg">
                  <FileSearch className="h-6 w-6 text-destructive" />
                </div>
                <h3 className="font-serif text-xl font-semibold text-primary">
                  Contradictions
                </h3>
              </div>
              <p className="text-foreground/80 mb-4">
                &ldquo;The witness said one thing on page 234. On page 1,847, he said the
                opposite.&rdquo;
              </p>
              <p className="text-sm text-muted-foreground font-medium">
                Caught across 2000 pages.
              </p>
            </div>

            {/* Timeline Problems */}
            <div className="bg-card border border-border rounded-lg p-6 shadow-sm">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-accent/10 rounded-lg">
                  <Clock className="h-6 w-6 text-accent" />
                </div>
                <h3 className="font-serif text-xl font-semibold text-primary">
                  Timeline Problems
                </h3>
              </div>
              <p className="text-foreground/80 mb-4">
                &ldquo;This document was supposedly signed two days before it existed.&rdquo;
              </p>
              <p className="text-sm text-muted-foreground font-medium">
                Impossible dates, flagged automatically.
              </p>
            </div>

            {/* Entity Tracking */}
            <div className="bg-card border border-border rounded-lg p-6 shadow-sm">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <Users className="h-6 w-6 text-primary" />
                </div>
                <h3 className="font-serif text-xl font-semibold text-primary">
                  Entity Tracking
                </h3>
              </div>
              <p className="text-foreground/80 mb-4">
                &ldquo;Sharma&rdquo; = &ldquo;R.K. Sharma&rdquo; = &ldquo;Mr. Sharma&rdquo; =
                &ldquo;the respondent&rdquo;
              </p>
              <p className="text-sm text-muted-foreground font-medium">
                All linked automatically, no matter how they appear.
              </p>
            </div>
          </div>

          <p className="text-center mt-10 text-lg font-medium text-primary">
            Every finding links to the source document and page.
            <br />
            <span className="text-muted-foreground">
              If jaanch can&apos;t trace it back, it doesn&apos;t show it.
            </span>
          </p>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-20 px-6 bg-muted/30">
        <div className="max-w-5xl mx-auto">
          <h2 className="font-serif text-3xl md:text-4xl font-bold text-primary mb-4 text-center">
            Three steps. Every finding cited.
          </h2>
          <p className="text-center text-muted-foreground mb-12 text-lg">
            From upload to insights in minutes, not days
          </p>

          <div className="grid md:grid-cols-3 gap-8">
            {/* Step 1 */}
            <div className="text-center">
              <div className="w-16 h-16 bg-primary text-primary-foreground rounded-full flex items-center justify-center mx-auto mb-6 text-2xl font-bold font-serif">
                1
              </div>
              <h3 className="font-serif text-xl font-semibold text-primary mb-4">
                Upload your case files
              </h3>
              <p className="text-foreground/80">
                Drop your PDFs — even messy scans, ZIPs with hundreds of documents. Our AI
                reads everything.
              </p>
            </div>

            {/* Step 2 */}
            <div className="text-center">
              <div className="w-16 h-16 bg-primary text-primary-foreground rounded-full flex items-center justify-center mx-auto mb-6 text-2xl font-bold font-serif">
                2
              </div>
              <h3 className="font-serif text-xl font-semibold text-primary mb-4">
                AI analyzes everything
              </h3>
              <p className="text-foreground/80 mb-4">
                jaanch runs 4 specialized engines in parallel:
              </p>
              <ul className="text-sm text-muted-foreground space-y-2 text-left max-w-xs mx-auto">
                <li className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-accent" />
                  <span>
                    <strong>Timeline</strong> — Extracts dates, builds chronology
                  </span>
                </li>
                <li className="flex items-center gap-2">
                  <Users className="h-4 w-4 text-primary" />
                  <span>
                    <strong>Entities</strong> — Maps people, companies
                  </span>
                </li>
                <li className="flex items-center gap-2">
                  <Scale className="h-4 w-4 text-destructive" />
                  <span>
                    <strong>Citations</strong> — Finds every Act reference
                  </span>
                </li>
                <li className="flex items-center gap-2">
                  <FileSearch className="h-4 w-4 text-destructive" />
                  <span>
                    <strong>Contradictions</strong> — Spots conflicts
                  </span>
                </li>
              </ul>
            </div>

            {/* Step 3 */}
            <div className="text-center">
              <div className="w-16 h-16 bg-primary text-primary-foreground rounded-full flex items-center justify-center mx-auto mb-6 text-2xl font-bold font-serif">
                3
              </div>
              <h3 className="font-serif text-xl font-semibold text-primary mb-4">
                Review cited findings
              </h3>
              <p className="text-foreground/80">
                Every finding is tied to the exact document, page, and line. Nothing vague —
                you verify, you decide.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ChatGPT vs jaanch Section */}
      <section className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <h2 className="font-serif text-3xl md:text-4xl font-bold text-primary mb-4 text-center">
            ChatGPT summarizes. jaanch verifies.
          </h2>
          <p className="text-center text-muted-foreground mb-12">
            AI that sounds right vs. AI that is right
          </p>

          {/* Side-by-side comparison cards */}
          <div className="grid md:grid-cols-2 gap-6 mb-12">
            {/* ChatGPT side */}
            <div className="bg-muted/30 rounded-lg p-6 border border-border/50">
              <h3 className="font-serif text-lg font-semibold text-muted-foreground mb-4 flex items-center gap-2">
                <XCircle className="h-5 w-5 text-destructive" />
                Generic AI
              </h3>
              <ul className="space-y-3 text-foreground/70">
                <li className="flex items-start gap-2">
                  <span className="text-destructive mt-1">✗</span>
                  <span>&ldquo;The parties dispute ownership...&rdquo;</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-destructive mt-1">✗</span>
                  <span>No citations, no page numbers</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-destructive mt-1">✗</span>
                  <span>Hallucinations possible</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-destructive mt-1">✗</span>
                  <span>Confident even when wrong</span>
                </li>
              </ul>
            </div>

            {/* jaanch side */}
            <div className="bg-card rounded-lg p-6 border-2 border-primary/20 shadow-sm">
              <h3 className="font-serif text-lg font-semibold text-primary mb-4 flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-success" />
                jaanch.ai
              </h3>
              <ul className="space-y-3 text-foreground">
                <li className="flex items-start gap-2">
                  <span className="text-success mt-1">✓</span>
                  <span>&ldquo;Party A claims X on <strong>Page 45</strong>, but states Y on <strong>Page 312</strong>&rdquo;</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-success mt-1">✓</span>
                  <span>Every finding cited to exact page & line</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-success mt-1">✓</span>
                  <span>Evidence-bound — no hallucinations</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-accent mt-1">!</span>
                  <span>Says &ldquo;I don&apos;t know&rdquo; when unsure</span>
                </li>
              </ul>
            </div>
          </div>

          {/* Trust Statement */}
          <div className="bg-primary/5 border border-primary/10 rounded-lg p-6 text-center max-w-2xl mx-auto">
            <p className="text-lg text-foreground/80">
              If jaanch can&apos;t trace it back to a source document,
              <span className="font-semibold text-primary"> it doesn&apos;t show it.</span>
            </p>
          </div>
        </div>
      </section>

      {/* Who It's For Section */}
      <section className="py-16 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-10">
            <h2 className="font-serif text-3xl md:text-4xl font-bold text-primary mb-3">
              700 pages. 48 hours.
            </h2>
            <p className="text-xl text-foreground/80">
              jaanch finds the patterns. You verify and win.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-4">
            <div className="bg-card border border-border rounded-lg p-5 text-center">
              <h3 className="font-serif text-lg font-semibold text-primary mb-2">
                Junior Lawyers
              </h3>
              <p className="text-sm text-foreground/70">
                Find what matters in hours, not days.
              </p>
            </div>

            <div className="bg-card border border-border rounded-lg p-5 text-center">
              <h3 className="font-serif text-lg font-semibold text-primary mb-2">
                Senior Lawyers
              </h3>
              <p className="text-sm text-foreground/70">
                Validate research in minutes. Every finding cited.
              </p>
            </div>

            <div className="bg-card border border-border rounded-lg p-5 text-center">
              <h3 className="font-serif text-lg font-semibold text-primary mb-2">
                Law Firms
              </h3>
              <p className="text-sm text-foreground/70">
                Better outcomes. Reduced risk. Work smarter.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Built By Section */}
      <section className="py-12 px-6 bg-muted/30">
        <div className="max-w-3xl mx-auto text-center">
          <p className="text-muted-foreground mb-2">Built for lawyers who can&apos;t afford to miss anything</p>
          <p className="text-foreground/80">
            <strong>Juhi Nebhnani</strong> and <strong>Siddhi Maheshwari</strong> • 100xEngineers
          </p>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 px-6 bg-primary text-primary-foreground">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="font-serif text-3xl md:text-4xl font-bold mb-6">
            What if you could walk into court knowing you&apos;ve found every gap in the
            other side&apos;s story?
          </h2>
          <p className="text-xl mb-10 opacity-90">
            That&apos;s jaanch.ai. Verify, don&apos;t trust.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/signup">
              <Button
                size="lg"
                variant="secondary"
                className="text-lg px-8 py-6 h-auto bg-white text-primary hover:bg-white/90"
              >
                See what you&apos;re missing
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
            <Link href="/contact">
              <Button
                size="lg"
                variant="outline"
                className="text-lg px-8 py-6 h-auto border-white/30 text-white hover:bg-white/10"
              >
                Book a demo for your firm
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-10 px-6 border-t border-border">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Image
              src="/logo-full.png"
              alt="jaanch.ai"
              width={100}
              height={26}
              className="h-6 w-auto"
              style={{ width: 'auto', height: 'auto' }}
            />
          </div>
          <p className="text-sm text-muted-foreground">
            &copy; {new Date().getFullYear()} jaanch.ai. All rights reserved.
          </p>
          <div className="flex items-center gap-6 text-sm text-muted-foreground">
            <Link href="/privacy" className="hover:text-foreground transition-colors">
              Privacy
            </Link>
            <Link href="/terms" className="hover:text-foreground transition-colors">
              Terms
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
