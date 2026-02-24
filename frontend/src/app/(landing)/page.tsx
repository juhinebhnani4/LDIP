import Image from "next/image"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import {
  Scale,
  FileSearch,
  Clock,
  Users,
  AlertTriangle,
  ArrowRight,
  MessageSquare,
  Shield,
  Search,
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
                Ask your case files
                <br />
                <span className="text-accent">anything.</span>
              </h1>
              <p className="text-lg text-muted-foreground mb-3 font-medium">
                Get answers with the page number.
              </p>
              <p className="text-lg text-foreground/80 mb-8 leading-relaxed">
                Upload your case files. Ask jaanch a question. It searches across
                every document and gives you cited answers — with the document
                name and page.
              </p>
              <Link href="/signup">
                <Button
                  size="lg"
                  className="bg-primary text-primary-foreground hover:bg-primary/90 text-lg px-8 py-6 h-auto"
                >
                  Try it on your case files
                  <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
              </Link>
            </div>

            {/* Right: Chat Interaction Mockup */}
            <div className="relative">
              <div className="absolute -top-4 -left-4 w-full h-full bg-muted/50 rounded-lg transform rotate-2" />
              <div className="absolute -top-2 -left-2 w-full h-full bg-muted/30 rounded-lg transform rotate-1" />

              <div className="relative bg-card border border-border rounded-lg shadow-lg overflow-hidden">
                {/* Chat header */}
                <div className="bg-primary/5 border-b border-border px-4 py-3 flex items-center gap-2">
                  <MessageSquare className="h-4 w-4 text-primary" />
                  <span className="text-sm font-semibold text-primary">jaanch chat</span>
                  <span className="text-xs text-muted-foreground ml-auto">3 documents uploaded</span>
                </div>

                <div className="p-5 space-y-4">
                  {/* User question */}
                  <div className="flex justify-end">
                    <div className="bg-primary text-primary-foreground rounded-lg rounded-br-sm px-4 py-2.5 max-w-[85%]">
                      <p className="text-sm">
                        What did the respondent say about the share transfer?
                      </p>
                    </div>
                  </div>

                  {/* AI answer */}
                  <div className="bg-muted/50 rounded-lg rounded-bl-sm p-4 space-y-3">
                    <p className="text-sm text-foreground leading-relaxed">
                      The respondent&apos;s position on the share transfer is stated differently
                      across two documents:
                    </p>
                    <p className="text-sm text-foreground leading-relaxed">
                      In the <strong>Affidavit</strong> (p. 47), the respondent claims the shares
                      were transferred on{" "}
                      <span className="bg-accent/20 px-1 font-medium">15th March 2018</span>{" "}
                      with the petitioner&apos;s consent.
                    </p>
                    <p className="text-sm text-foreground leading-relaxed">
                      However, in the <strong>Company Letter</strong> (p. 12), the company states
                      that no transfer occurred until{" "}
                      <span className="bg-accent/20 px-1 font-medium">22nd August 2019</span>.
                    </p>

                    {/* Source buttons */}
                    <div className="flex flex-wrap gap-2 pt-2 border-t border-border">
                      <span className="text-xs font-mono bg-primary/10 text-primary px-2 py-1 rounded cursor-pointer hover:bg-primary/20 transition-colors">
                        Affidavit_2019.pdf &middot; p. 47
                      </span>
                      <span className="text-xs font-mono bg-primary/10 text-primary px-2 py-1 rounded cursor-pointer hover:bg-primary/20 transition-colors">
                        Company_Letter.pdf &middot; p. 12
                      </span>
                    </div>

                    {/* Contradiction flag */}
                    <div className="flex items-center gap-2 text-xs text-destructive bg-destructive/5 px-3 py-1.5 rounded">
                      <AlertTriangle className="h-3.5 w-3.5" />
                      <span className="font-medium">Contradiction detected — dates differ by 17 months</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Problem Section */}
      <section className="py-20 px-6 bg-muted/30">
        <div className="max-w-5xl mx-auto">
          <div className="grid lg:grid-cols-5 gap-10 items-center">
            {/* Left: Document stack visual */}
            <div className="lg:col-span-2 flex justify-center">
              <div className="relative w-48 h-64">
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
                <div className="absolute -bottom-4 -right-4 bg-primary text-primary-foreground text-sm font-bold px-3 py-1 rounded-full shadow-lg z-10">
                  700+ pages
                </div>
              </div>
            </div>

            {/* Right: Copy */}
            <div className="lg:col-span-3">
              <h2 className="font-serif text-3xl md:text-4xl font-bold text-primary mb-6">
                700 pages. 15 years of documents.
                <br />
                <span className="text-accent">A hearing next week.</span>
              </h2>
              <div className="space-y-4 text-foreground/80">
                <p>
                  A Special Court dispute. 25 years of documents. Affidavits,
                  company letters, court orders.
                </p>
                <p>
                  Names that appear differently across filings. Dates scattered
                  across hundreds of pages. Cross-references between documents
                  that span decades.
                </p>
                <p className="font-medium text-foreground">
                  jaanch reads it all and lets you search across everything.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Product Mockups Section */}
      <section className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <h2 className="font-serif text-3xl md:text-4xl font-bold text-primary mb-4 text-center">
            See what jaanch gives you
          </h2>
          <p className="text-center text-muted-foreground mb-12 text-lg">
            Document names, page numbers, everything cited.
          </p>

          <div className="grid md:grid-cols-3 gap-6">
            {/* Chat Mockup */}
            <div className="bg-card border border-border rounded-lg shadow-sm overflow-hidden">
              <div className="bg-primary/5 border-b border-border px-4 py-2.5 flex items-center gap-2">
                <Search className="h-4 w-4 text-primary" />
                <span className="text-sm font-semibold text-primary">Search &amp; Chat</span>
              </div>
              <div className="p-4 space-y-3">
                <div className="flex justify-end">
                  <div className="bg-primary/10 rounded-lg px-3 py-2 text-xs text-foreground">
                    What did the respondent say about the share transfer?
                  </div>
                </div>
                <div className="bg-muted/50 rounded-lg p-3 space-y-2">
                  <p className="text-xs text-foreground leading-relaxed">
                    In the <strong>Affidavit</strong> (p. 47), the respondent claims
                    the shares were transferred on 15th March 2018...
                  </p>
                  <p className="text-xs text-foreground leading-relaxed">
                    However, in the <strong>Company Letter</strong> (p. 12), the
                    company states no transfer occurred until 22nd August 2019.
                  </p>
                  <div className="flex flex-wrap gap-1.5 pt-2 border-t border-border">
                    <span className="text-[10px] font-mono bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                      Affidavit &middot; p. 47
                    </span>
                    <span className="text-[10px] font-mono bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                      Company Letter &middot; p. 12
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Timeline Mockup */}
            <div className="bg-card border border-border rounded-lg shadow-sm overflow-hidden">
              <div className="bg-accent/5 border-b border-border px-4 py-2.5 flex items-center gap-2">
                <Clock className="h-4 w-4 text-accent" />
                <span className="text-sm font-semibold text-primary">Timeline</span>
              </div>
              <div className="p-4 space-y-3">
                {/* Timeline events */}
                <div className="relative pl-4 border-l-2 border-primary/20 space-y-3">
                  <div>
                    <p className="text-[10px] font-mono text-muted-foreground">12 Jan 2016</p>
                    <p className="text-xs text-foreground">Notice issued to respondent</p>
                    <p className="text-[10px] text-muted-foreground">Court Order &middot; p. 3</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-mono text-muted-foreground">15 Mar 2018</p>
                    <p className="text-xs text-foreground">Shares transferred to petitioner</p>
                    <p className="text-[10px] text-muted-foreground">Affidavit &middot; p. 47</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-mono text-muted-foreground">22 Aug 2019</p>
                    <p className="text-xs text-foreground">Company denies any transfer</p>
                    <p className="text-[10px] text-muted-foreground">Company Letter &middot; p. 12</p>
                  </div>
                </div>
                {/* Anomaly */}
                <div className="flex items-center gap-1.5 text-[10px] text-accent bg-accent/5 px-2 py-1 rounded">
                  <AlertTriangle className="h-3 w-3" />
                  <span className="font-medium">3-year gap between notice and filing</span>
                </div>
              </div>
            </div>

            {/* Entity Mockup */}
            <div className="bg-card border border-border rounded-lg shadow-sm overflow-hidden">
              <div className="bg-primary/5 border-b border-border px-4 py-2.5 flex items-center gap-2">
                <Users className="h-4 w-4 text-primary" />
                <span className="text-sm font-semibold text-primary">Entities</span>
              </div>
              <div className="p-4 space-y-3">
                {/* Entity group */}
                <div className="bg-muted/50 rounded-lg p-3 space-y-2">
                  <p className="text-xs font-semibold text-foreground">R.K. Sharma</p>
                  <div className="flex flex-wrap gap-1.5">
                    <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                      &ldquo;Sharma&rdquo;
                    </span>
                    <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                      &ldquo;R.K. Sharma&rdquo;
                    </span>
                    <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                      &ldquo;the respondent&rdquo;
                    </span>
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    Appears in 4 documents &middot; 23 mentions
                  </p>
                </div>
                <div className="bg-muted/50 rounded-lg p-3 space-y-2">
                  <p className="text-xs font-semibold text-foreground">Apex Holdings Ltd.</p>
                  <div className="flex flex-wrap gap-1.5">
                    <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                      &ldquo;Apex Holdings&rdquo;
                    </span>
                    <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">
                      &ldquo;the Company&rdquo;
                    </span>
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    Appears in 3 documents &middot; 15 mentions
                  </p>
                </div>
                <p className="text-[10px] text-muted-foreground text-center">
                  Aliases linked automatically. You verify.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* What Else jaanch Surfaces — Engines Section */}
      <section className="py-20 px-6 bg-muted/30">
        <div className="max-w-5xl mx-auto">
          <h2 className="font-serif text-3xl md:text-4xl font-bold text-primary mb-4 text-center">
            What else jaanch surfaces
          </h2>
          <p className="text-center text-muted-foreground mb-12 text-lg">
            These run automatically alongside search
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
                Flagged across thousands of pages.
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
                &ldquo;There&apos;s a 3-year gap between the notice and the filing.&rdquo;
              </p>
              <p className="text-sm text-muted-foreground font-medium">
                Unusual gaps and out-of-order events, flagged automatically.
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
                Linked automatically where possible. You verify the rest.
              </p>
            </div>
          </div>

          <p className="text-center mt-10 text-lg font-medium text-primary">
            You decide what matters. jaanch just puts it in front of you.
          </p>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <h2 className="font-serif text-3xl md:text-4xl font-bold text-primary mb-4 text-center">
            Three steps. Sources linked.
          </h2>
          <p className="text-center text-muted-foreground mb-12 text-lg">
            Upload. Process. Review.
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
                Drop your PDFs — even messy scans, ZIPs with hundreds of documents.
              </p>
              <p className="text-xs text-muted-foreground mt-3">
                Files are encrypted, stored privately, and isolated per matter. AI models don&apos;t train on your data.
              </p>
            </div>

            {/* Step 2 */}
            <div className="text-center">
              <div className="w-16 h-16 bg-primary text-primary-foreground rounded-full flex items-center justify-center mx-auto mb-6 text-2xl font-bold font-serif">
                2
              </div>
              <h3 className="font-serif text-xl font-semibold text-primary mb-4">
                jaanch processes your documents
              </h3>
              <p className="text-foreground/80 mb-4">
                4 engines run in parallel, plus a search index across everything:
              </p>
              <ul className="text-sm text-muted-foreground space-y-2 text-left max-w-xs mx-auto">
                <li className="flex items-center gap-2">
                  <Search className="h-4 w-4 text-primary" />
                  <span>
                    <strong>Search</strong> — Ask anything, get cited answers
                  </span>
                </li>
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
                    <strong>Citations</strong> — Finds Act references
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
                Ask questions, review findings
              </h3>
              <p className="text-foreground/80">
                Every answer and finding is tied to a document and page. Nothing vague —
                you verify, you decide.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* What jaanch Gives You Section */}
      <section className="py-20 px-6 bg-muted/30">
        <div className="max-w-4xl mx-auto">
          <h2 className="font-serif text-3xl md:text-4xl font-bold text-primary mb-10 text-center">
            What jaanch gives you.
          </h2>

          <div className="space-y-4 max-w-2xl mx-auto">
            <div className="flex items-start gap-3">
              <Search className="h-5 w-5 text-primary mt-0.5 shrink-0" />
              <p className="text-foreground/80 text-lg">
                Ask a question about your case files — get an answer with the document and page.
              </p>
            </div>
            <div className="flex items-start gap-3">
              <Clock className="h-5 w-5 text-accent mt-0.5 shrink-0" />
              <p className="text-foreground/80 text-lg">
                A chronology built from every date across every document.
              </p>
            </div>
            <div className="flex items-start gap-3">
              <Users className="h-5 w-5 text-primary mt-0.5 shrink-0" />
              <p className="text-foreground/80 text-lg">
                Names and aliases linked across filings.
              </p>
            </div>
            <div className="flex items-start gap-3">
              <FileSearch className="h-5 w-5 text-destructive mt-0.5 shrink-0" />
              <p className="text-foreground/80 text-lg">
                Contradictions and citation issues flagged with sources.
              </p>
            </div>
          </div>

          <p className="text-center mt-10 text-foreground/70">
            You already do the hard work. jaanch just makes some of it searchable.
          </p>

          {/* Trust Statement */}
          <div className="bg-primary/5 border border-primary/10 rounded-lg p-6 text-center max-w-2xl mx-auto mt-8">
            <p className="text-lg text-foreground/80">
              If jaanch can&apos;t trace it back to a source document,
              <span className="font-semibold text-primary"> it tells you.</span>
            </p>
          </div>
        </div>
      </section>

      {/* Who It's For Section */}
      <section className="py-16 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-10">
            <h2 className="font-serif text-3xl md:text-4xl font-bold text-primary mb-3">
              A hearing on Monday. A mountain of files.
            </h2>
            <p className="text-xl text-foreground/80">
              jaanch surfaces the patterns. You decide what to do with them.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-4">
            <div className="bg-card border border-border rounded-lg p-5 text-center">
              <h3 className="font-serif text-lg font-semibold text-primary mb-2">
                Junior Lawyers
              </h3>
              <p className="text-sm text-foreground/70">
                Get a head start on what to look for.
              </p>
            </div>

            <div className="bg-card border border-border rounded-lg p-5 text-center">
              <h3 className="font-serif text-lg font-semibold text-primary mb-2">
                Senior Lawyers
              </h3>
              <p className="text-sm text-foreground/70">
                Validate research faster. Findings are cited.
              </p>
            </div>

            <div className="bg-card border border-border rounded-lg p-5 text-center">
              <h3 className="font-serif text-lg font-semibold text-primary mb-2">
                Law Firms
              </h3>
              <p className="text-sm text-foreground/70">
                Less time searching. More time building arguments.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Trust Section */}
      <section className="py-10 px-6 bg-muted/30">
        <div className="max-w-4xl mx-auto">
          <div className="grid md:grid-cols-3 gap-6 text-center">
            <div className="flex flex-col items-center gap-2">
              <Shield className="h-5 w-5 text-primary" />
              <p className="text-sm text-foreground/80">
                Your files are stored in encrypted private storage, isolated per matter.
              </p>
            </div>
            <div className="flex flex-col items-center gap-2">
              <Shield className="h-5 w-5 text-primary" />
              <p className="text-sm text-foreground/80">
                Documents are sent to AI for processing — not for training.
              </p>
            </div>
            <div className="flex flex-col items-center gap-2">
              <Shield className="h-5 w-5 text-primary" />
              <p className="text-sm text-foreground/80">
                Each matter is access-controlled. Nobody sees your files but you.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Built By Section */}
      <section className="py-12 px-6">
        <div className="max-w-3xl mx-auto text-center">
          <p className="text-foreground/80">
            Built by <strong>Juhi Nebhnani</strong> and <strong>Siddhi Maheshwari</strong>.
            We&apos;re not lawyers — we built this after seeing how much work goes into
            reading case files.
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Your method, your files. jaanch just makes them searchable.
          </p>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 px-6 bg-primary text-primary-foreground">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="font-serif text-3xl md:text-4xl font-bold mb-6">
            What if you had one more way to spot the gaps in the
            other side&apos;s story?
          </h2>
          <p className="text-xl mb-4 opacity-90">
            That&apos;s jaanch. One more tool in your corner.
          </p>
          <p className="text-base mb-10 opacity-70">
            Free during early access. Help us build it how you want it.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/signup">
              <Button
                size="lg"
                variant="secondary"
                className="text-lg px-8 py-6 h-auto bg-white text-primary hover:bg-white/90"
              >
                Try it on your case files
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
            <Link href="/contact">
              <Button
                size="lg"
                variant="outline"
                className="text-lg px-8 py-6 h-auto border-2 border-white !text-white hover:bg-white/10 bg-transparent"
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
