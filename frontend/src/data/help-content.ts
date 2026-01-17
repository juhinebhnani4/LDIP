export interface HelpEntry {
  id: string;
  title: string;
  category: 'getting-started' | 'documents' | 'timeline' | 'chat' | 'export' | 'troubleshooting' | 'citations' | 'contradictions' | 'entities';
  content: string;
  keywords: string[];
  relatedTopics?: string[];
}

export const helpCategories = {
  'getting-started': {
    label: 'Getting Started',
    description: 'Learn the basics of using jaanch.ai',
  },
  documents: {
    label: 'Documents',
    description: 'Upload, view, and manage your case documents',
  },
  timeline: {
    label: 'Timeline',
    description: 'Understand the extracted timeline of events',
  },
  chat: {
    label: 'Chat & Q&A',
    description: 'Ask questions about your documents',
  },
  citations: {
    label: 'Citations',
    description: 'Legal citations and references',
  },
  contradictions: {
    label: 'Contradictions',
    description: 'Find inconsistencies in your documents',
  },
  entities: {
    label: 'Entities',
    description: 'People, organizations, and key terms',
  },
  export: {
    label: 'Export',
    description: 'Export your findings and reports',
  },
  troubleshooting: {
    label: 'Troubleshooting',
    description: 'Common issues and solutions',
  },
} as const;

export const helpContent: HelpEntry[] = [
  // Getting Started
  {
    id: 'welcome',
    title: 'Welcome to jaanch.ai',
    category: 'getting-started',
    content: `## Welcome to jaanch.ai

jaanch.ai is an AI-powered legal document intelligence platform designed to help attorneys analyze case documents efficiently.

### Key Features

- **Document Analysis**: Upload PDFs, Word documents, and images for automatic OCR and analysis
- **Timeline Extraction**: Automatically extract and visualize events from your documents
- **Smart Q&A**: Ask natural language questions about your case documents
- **Citation Detection**: Identify legal citations and verify their accuracy
- **Contradiction Detection**: Find inconsistencies across documents

### Quick Start

1. Create or select a matter from the dashboard
2. Upload your case documents
3. Wait for processing to complete
4. Explore the analysis tabs: Summary, Timeline, Documents, Citations, and more`,
    keywords: ['welcome', 'start', 'begin', 'introduction', 'overview', 'features'],
    relatedTopics: ['upload-documents', 'dashboard-overview'],
  },
  {
    id: 'dashboard-overview',
    title: 'Dashboard Overview',
    category: 'getting-started',
    content: `## Dashboard Overview

The dashboard is your home base in jaanch.ai, showing all your matters at a glance.

### Matter Cards

Each card represents a legal matter and displays:
- Matter name and status
- Document count
- Recent activity
- Quick access to the workspace

### Quick Actions

- **New Matter**: Click the "+" button to create a new matter
- **Search**: Use global search to find matters by name
- **Filter**: Filter by status, date, or other criteria

### Navigation

- Click any matter card to open its workspace
- Use the sidebar to access different sections`,
    keywords: ['dashboard', 'home', 'matters', 'cards', 'overview'],
    relatedTopics: ['welcome', 'creating-matter'],
  },
  {
    id: 'creating-matter',
    title: 'Creating a New Matter',
    category: 'getting-started',
    content: `## Creating a New Matter

A "matter" represents a legal case or project containing related documents.

### Steps to Create a Matter

1. Click the **"New Matter"** button on the dashboard
2. Enter a descriptive name for your matter
3. Upload your initial documents (optional)
4. Click **"Create"** to set up the matter

### Tips

- Use clear, descriptive names (e.g., "Smith v. Jones Contract Dispute")
- You can add more documents later
- Matter names can be edited after creation`,
    keywords: ['create', 'new', 'matter', 'case', 'project', 'setup'],
    relatedTopics: ['dashboard-overview', 'upload-documents'],
  },

  // Documents
  {
    id: 'upload-documents',
    title: 'Uploading Documents',
    category: 'documents',
    content: `## Uploading Documents

Upload your case documents for AI-powered analysis.

### Supported Formats

- **PDF** (recommended): Best for scanned documents
- **Images**: JPG, PNG, TIFF
- **Word Documents**: DOCX, DOC

### How to Upload

1. Navigate to the **Documents** tab in your matter
2. Click **"Upload"** or drag files into the drop zone
3. Review selected files before uploading
4. Wait for processing to complete

### Processing Time

- Simple PDFs: ~30 seconds per page
- Scanned documents: ~1 minute per page (includes OCR)
- Large files (100+ pages): May take several minutes

### Tips

- Higher quality scans produce better results
- Processing happens in the background - you can continue working`,
    keywords: ['upload', 'document', 'pdf', 'file', 'ocr', 'add', 'import'],
    relatedTopics: ['document-processing', 'supported-formats'],
  },
  {
    id: 'document-processing',
    title: 'Document Processing',
    category: 'documents',
    content: `## Document Processing

After upload, documents go through several analysis stages.

### Processing Stages

1. **OCR** (Optical Character Recognition): Extracts text from images/scans
2. **Structure Analysis**: Identifies pages, sections, paragraphs
3. **Entity Extraction**: Finds people, organizations, dates
4. **Timeline Extraction**: Identifies events and dates
5. **Citation Detection**: Finds legal citations

### OCR Quality

Documents receive a quality score:
- **High (90%+)**: Clear text, good for analysis
- **Medium (70-89%)**: May have some errors
- **Low (<70%)**: Consider uploading a better scan

### Viewing Progress

The progress indicator shows real-time status. Click on a processing document to see detailed progress.`,
    keywords: ['processing', 'ocr', 'extract', 'analyze', 'quality', 'status'],
    relatedTopics: ['upload-documents', 'ocr-quality'],
  },
  {
    id: 'ocr-quality',
    title: 'OCR Quality Explained',
    category: 'documents',
    content: `## OCR Quality

OCR (Optical Character Recognition) quality affects the accuracy of document analysis.

### Quality Levels

| Score | Level | Meaning |
|-------|-------|---------|
| 90%+ | High | Excellent text recognition |
| 70-89% | Medium | Good, with minor errors |
| <70% | Low | Significant errors possible |

### Improving Quality

- Use high-resolution scans (300 DPI recommended)
- Ensure good contrast (dark text on light background)
- Avoid skewed or rotated pages
- For handwritten documents, print clearly

### Manual Review

Low-quality documents are flagged for manual review. You can verify and correct extracted text.`,
    keywords: ['ocr', 'quality', 'scan', 'recognition', 'accuracy', 'dpi'],
    relatedTopics: ['document-processing', 'manual-review'],
  },

  // Timeline
  {
    id: 'timeline-overview',
    title: 'Timeline Overview',
    category: 'timeline',
    content: `## Timeline Overview

The timeline automatically extracts and displays events from your documents.

### What Gets Extracted

- Dated events mentioned in documents
- Key milestones and deadlines
- Contract dates and terms
- Meeting notes and correspondence dates

### Timeline Views

- **Horizontal**: See events on a scrollable timeline
- **Vertical**: List view with full event details
- **Zoom**: Adjust the time scale (day/week/month/year)

### Event Cards

Each event shows:
- Date (or date range)
- Event description
- Source document
- Confidence level`,
    keywords: ['timeline', 'events', 'dates', 'chronology', 'history'],
    relatedTopics: ['event-details', 'timeline-filters'],
  },
  {
    id: 'event-details',
    title: 'Viewing Event Details',
    category: 'timeline',
    content: `## Event Details

Click any event on the timeline to see full details.

### Event Information

- **Date**: When the event occurred
- **Description**: What happened
- **Source**: The document where this was found
- **Page**: Specific page reference
- **Confidence**: How certain the AI is about this extraction

### Actions

- **View Source**: Jump to the exact location in the document
- **Edit**: Correct or refine event details
- **Verify**: Mark as verified after review
- **Flag**: Mark for further investigation`,
    keywords: ['event', 'details', 'source', 'page', 'verify'],
    relatedTopics: ['timeline-overview', 'verification'],
  },

  // Chat & Q&A
  {
    id: 'chat-basics',
    title: 'Using the Chat Panel',
    category: 'chat',
    content: `## Chat Panel

Ask questions about your documents in natural language.

### How to Use

1. Open the chat panel on the right side of the workspace
2. Type your question in natural language
3. Press Enter or click Send
4. View the AI-generated response with citations

### Example Questions

- "When was the contract signed?"
- "What are the key terms of the agreement?"
- "Who are the parties involved?"
- "Were there any amendments to the original agreement?"

### Response Features

- **Citations**: Click to see the source document
- **Confidence Scores**: See how certain the AI is
- **Follow-up Questions**: Suggested related questions`,
    keywords: ['chat', 'ask', 'question', 'answer', 'query', 'qa'],
    relatedTopics: ['hybrid-search', 'citations-in-chat'],
  },
  {
    id: 'hybrid-search',
    title: 'Hybrid Search Explained',
    category: 'chat',
    content: `## Hybrid Search

jaanch.ai uses hybrid search to find the best answers.

### What is Hybrid Search?

Hybrid search combines two approaches:
1. **Semantic Search**: Understands meaning and context
2. **Keyword Search**: Finds exact word matches

### Benefits

- Better results for complex legal questions
- Finds related concepts even with different wording
- Catches exact citations and legal terms

### Search Modes

- **Auto**: System chooses the best approach (recommended)
- **Semantic**: Prioritizes meaning over exact words
- **Keyword**: Prioritizes exact matches`,
    keywords: ['hybrid', 'search', 'semantic', 'keyword', 'find', 'query'],
    relatedTopics: ['chat-basics', 'search-tips'],
  },

  // Citations
  {
    id: 'citations-overview',
    title: 'Citations Tab Overview',
    category: 'citations',
    content: `## Citations Tab

The Citations tab shows all legal citations found in your documents.

### What Gets Detected

- Case law citations (e.g., "Smith v. Jones, 123 F.3d 456")
- Statutory citations (e.g., "42 U.S.C. Section 1983")
- Regulatory citations
- Internal document references

### Citation Information

- Citation text
- Source document and page
- Verification status
- Related citations

### Actions

- **Verify**: Confirm citation accuracy
- **View Source**: See citation in context
- **Export**: Export citations list`,
    keywords: ['citation', 'case', 'statute', 'reference', 'law', 'legal'],
    relatedTopics: ['citation-verification', 'act-discovery'],
  },
  {
    id: 'citation-verification',
    title: 'Verifying Citations',
    category: 'citations',
    content: `## Citation Verification

Verify that extracted citations are accurate and correctly identified.

### Verification Status

- **Unverified**: Not yet reviewed
- **Verified**: Confirmed as accurate
- **Flagged**: Needs attention or correction

### How to Verify

1. Click on a citation to see details
2. Review the source text
3. Check the citation format
4. Click "Verify" or "Flag" as appropriate

### Bulk Actions

- Select multiple citations
- Apply batch verification
- Export verified citations only`,
    keywords: ['verify', 'verification', 'confirm', 'review', 'accuracy'],
    relatedTopics: ['citations-overview', 'confidence-scores'],
  },

  // Contradictions
  {
    id: 'contradictions-overview',
    title: 'Contradictions Detection',
    category: 'contradictions',
    content: `## Contradictions Detection

Find inconsistencies and conflicting statements across your documents.

### What Gets Flagged

- Conflicting dates or timelines
- Contradictory statements
- Inconsistent facts
- Discrepancies between documents

### Severity Levels

- **High**: Major contradiction requiring attention
- **Medium**: Notable discrepancy
- **Low**: Minor inconsistency

### Reviewing Contradictions

Click any contradiction to see:
- The conflicting statements
- Source documents
- Suggested resolution`,
    keywords: ['contradiction', 'conflict', 'inconsistency', 'discrepancy', 'compare'],
    relatedTopics: ['contradiction-review', 'verification'],
  },
  {
    id: 'contradiction-review',
    title: 'Reviewing Contradictions',
    category: 'contradictions',
    content: `## Reviewing Contradictions

Efficiently review and resolve detected contradictions.

### Review Process

1. Open the Contradictions tab
2. Sort by severity (High first recommended)
3. Click to expand contradiction details
4. Review both statements in context
5. Mark as "Resolved", "Confirmed", or "False Positive"

### Resolution Options

- **Resolved**: Contradiction addressed in case strategy
- **Confirmed**: Valid contradiction, kept for reference
- **False Positive**: Not actually a contradiction

### Tips

- Review high-severity contradictions first
- Check the source documents for context
- Add notes to explain your resolution`,
    keywords: ['review', 'resolve', 'contradiction', 'false positive', 'confirm'],
    relatedTopics: ['contradictions-overview', 'export-findings'],
  },

  // Entities
  {
    id: 'entities-overview',
    title: 'Entities Tab Overview',
    category: 'entities',
    content: `## Entities Tab

View all people, organizations, and key terms extracted from your documents.

### Entity Types

- **People**: Names of individuals
- **Organizations**: Companies, agencies, courts
- **Locations**: Addresses, cities, countries
- **Dates**: Key dates and deadlines
- **Money**: Financial amounts
- **Legal Terms**: Specific legal terminology

### Entity Information

- Name and type
- Number of mentions
- Source documents
- Related entities

### Actions

- Click to see all mentions
- Link related entities
- Add notes or tags`,
    keywords: ['entity', 'person', 'organization', 'name', 'term', 'extract'],
    relatedTopics: ['entity-relationships', 'search-by-entity'],
  },

  // Export
  {
    id: 'export-overview',
    title: 'Exporting Your Work',
    category: 'export',
    content: `## Export Options

Export your findings and analysis for use outside jaanch.ai.

### What Can Be Exported

- Matter summary
- Timeline events
- Citations list
- Contradictions report
- Entity list
- Q&A session history

### Export Formats

- **PDF**: For sharing and printing
- **CSV**: For spreadsheet analysis
- **JSON**: For integration with other tools

### Confidence Thresholds

- High confidence (90%+): Export without warning
- Medium confidence (70-90%): Warning displayed
- Low confidence (<70%): Verification required before export`,
    keywords: ['export', 'download', 'pdf', 'csv', 'report', 'share'],
    relatedTopics: ['verification', 'confidence-scores'],
  },

  // Troubleshooting
  {
    id: 'slow-processing',
    title: 'Slow Document Processing',
    category: 'troubleshooting',
    content: `## Slow Document Processing

If documents are taking longer than expected to process:

### Possible Causes

- Large file size (100+ pages)
- Poor scan quality requiring extra OCR
- High system load

### Solutions

1. **Wait**: Large documents naturally take longer
2. **Check Status**: View the processing queue
3. **Split Files**: Break very large PDFs into smaller parts
4. **Improve Quality**: Rescan at higher resolution

### Processing Times

| Document Type | Expected Time |
|--------------|---------------|
| Simple PDF (<20 pages) | 1-2 minutes |
| Large PDF (50-100 pages) | 5-10 minutes |
| Scanned document | +50% additional time |`,
    keywords: ['slow', 'processing', 'time', 'waiting', 'stuck', 'long'],
    relatedTopics: ['document-processing', 'upload-documents'],
  },
  {
    id: 'poor-ocr-results',
    title: 'Poor OCR Results',
    category: 'troubleshooting',
    content: `## Poor OCR Results

If text extraction quality is low:

### Common Causes

- Low resolution scans
- Skewed or rotated pages
- Poor contrast
- Handwritten text
- Non-standard fonts

### Solutions

1. **Rescan**: Use 300 DPI or higher
2. **Straighten**: Ensure pages are aligned
3. **Enhance**: Increase contrast before scanning
4. **Manual Entry**: For critical handwritten text

### When to Re-upload

If OCR quality is below 70%, consider:
- Rescanning the original document
- Finding a digital version if available`,
    keywords: ['ocr', 'quality', 'poor', 'bad', 'wrong', 'error', 'text'],
    relatedTopics: ['ocr-quality', 'document-processing'],
  },
  {
    id: 'missing-data',
    title: 'Missing Extracted Data',
    category: 'troubleshooting',
    content: `## Missing Extracted Data

If expected information wasn't extracted:

### Check These First

1. **Processing Complete?**: Ensure all documents finished processing
2. **OCR Quality**: Low quality may miss content
3. **Document Format**: Some formats extract better than others

### Common Issues

- **Missing dates**: Check document date format
- **Missing names**: Unusual name formats may not be recognized
- **Missing citations**: Non-standard citation formats

### Manual Addition

You can always add missing information manually:
- Add events to the timeline
- Add entities
- Add notes and citations`,
    keywords: ['missing', 'not found', 'extract', 'wrong', 'incomplete'],
    relatedTopics: ['ocr-quality', 'document-processing', 'manual-review'],
  },
  {
    id: 'confidence-scores',
    title: 'Understanding Confidence Scores',
    category: 'troubleshooting',
    content: `## Confidence Scores

Confidence scores indicate how certain the AI is about extracted information.

### Score Ranges

| Score | Meaning | Recommendation |
|-------|---------|----------------|
| 90%+ | High confidence | Generally reliable |
| 70-89% | Medium confidence | Review recommended |
| <70% | Low confidence | Verification required |

### What Affects Confidence

- Document quality
- Clarity of language
- Context availability
- Training data coverage

### Using Confidence Scores

- Sort by confidence to prioritize review
- Low scores aren't necessarily wrong
- Verify critical information regardless of score`,
    keywords: ['confidence', 'score', 'accuracy', 'certain', 'reliable', 'trust'],
    relatedTopics: ['verification', 'export-overview'],
  },
];

export function searchHelpContent(query: string): HelpEntry[] {
  const normalizedQuery = query.toLowerCase().trim();
  if (!normalizedQuery) return [];

  return helpContent.filter((entry) => {
    const searchFields = [
      entry.title.toLowerCase(),
      entry.content.toLowerCase(),
      ...entry.keywords.map((k) => k.toLowerCase()),
    ];
    return searchFields.some((field) => field.includes(normalizedQuery));
  }).sort((a, b) => {
    const aExactMatch = a.keywords.some((k) => k.toLowerCase() === normalizedQuery);
    const bExactMatch = b.keywords.some((k) => k.toLowerCase() === normalizedQuery);
    if (aExactMatch && !bExactMatch) return -1;
    if (bExactMatch && !aExactMatch) return 1;
    return 0;
  });
}

export function getHelpEntryById(id: string): HelpEntry | undefined {
  return helpContent.find((entry) => entry.id === id);
}

export function getHelpEntriesByCategory(category: HelpEntry['category']): HelpEntry[] {
  return helpContent.filter((entry) => entry.category === category);
}
