# Jaanch AI — Architecture Diagrams (Mermaid)

> Generated for debugging and personal understanding.
> Open in any Mermaid-compatible viewer (VS Code, GitHub, Notion, mermaid.live).

---

## 1. High-Level System Architecture

```mermaid
graph TB
    subgraph Client["Browser (Next.js 16 — Vercel)"]
        FE[Frontend App<br/>React 19 / Zustand / SWR]
    end

    subgraph External["External Services"]
        GDAI[Google Document AI<br/>OCR]
        OAI[OpenAI<br/>Embeddings + GPT-4o]
        VOY[Voyage AI<br/>Embeddings + Reranker]
        COH[Cohere<br/>Reranker]
        GEM[Google Gemini<br/>OCR Validation]
        ANTH[Anthropic Claude<br/>Reasoning Traces]
        EMAIL[Email Service<br/>SMTP Notifications]
    end

    subgraph Railway["Railway Cloud"]
        subgraph API["API Service (FastAPI)"]
            ROUTES[HTTP Routes<br/>180+ endpoints]
            WS[WebSocket<br/>Connection Manager]
        end

        subgraph Worker["Worker Service (Celery)"]
            DOC_TASKS[Document Tasks]
            ENGINE_TASKS[Engine Tasks<br/>Citations / Timeline / Contradictions]
            EMBED_TASKS[Embedding Tasks]
            EVAL_TASKS[Evaluation + Email Tasks]
            MAINT_TASKS[Maintenance Tasks]
        end

        REDIS[(Redis<br/>Broker + Cache + PubSub)]
    end

    subgraph Supabase["Supabase (Managed)"]
        PG[(PostgreSQL<br/>+ pgvector)]
        AUTH[Supabase Auth<br/>JWT]
        STORAGE[Supabase Storage<br/>PDF Files]
    end

    FE -->|REST API| ROUTES
    FE -->|WebSocket| WS
    FE -->|Auth / Token| AUTH
    FE -->|Direct Upload| STORAGE

    ROUTES -->|Enqueue tasks| REDIS
    ROUTES -->|Read/Write| PG
    ROUTES -->|Pub/Sub events| REDIS
    WS -->|Subscribe| REDIS

    REDIS -->|Consume tasks| Worker
    Worker -->|Read/Write| PG
    Worker -->|Store PDFs| STORAGE

    DOC_TASKS -->|OCR| GDAI
    EMBED_TASKS -->|Embed| OAI
    EMBED_TASKS -->|Embed| VOY
    ENGINE_TASKS -->|LLM Calls| OAI
    ENGINE_TASKS -->|LLM Calls| ANTH
    ENGINE_TASKS -->|Rerank| VOY
    ENGINE_TASKS -->|Rerank| COH
    DOC_TASKS -->|Validate OCR| GEM
    EVAL_TASKS -->|Send Emails| EMAIL

    style Client fill:#e8f4fd,stroke:#2196F3
    style Railway fill:#fff3e0,stroke:#FF9800
    style Supabase fill:#e8f5e9,stroke:#4CAF50
    style External fill:#fce4ec,stroke:#E91E63
```

---

## 2. Backend Module Map

```mermaid
graph TB
    subgraph API_LAYER["API Layer (app/api/) — 35 route files"]
        direction TB
        ROUTES_GROUP["Routes (180+ endpoints)<br/>35 route files"]
        DEPS["deps.py<br/>Auth + DI"]
        WS_GROUP["WebSocket<br/>connection_manager / redis_bridge / auth"]
    end

    subgraph CORE_LAYER["Core Layer (app/core/) — 21 modules"]
        direction TB
        CORE_CFG["config, security, exceptions,<br/>logging, correlation"]
        CORE_PERF["circuit_breaker, rate_limit,<br/>llm_rate_limiter, cache_control"]
        CORE_OCR["bbox_search, bbox_filter, ocr_cleaner,<br/>gemini_client, page_detection"]
        CORE_DATA["cost_tracking, pricing_loader, data_loader,<br/>data_quality, fuzzy_match, prompt_boundaries,<br/>reliability_logging"]
    end

    subgraph SERVICE_LAYER["Services Layer (app/services/) — 130+ modules"]
        direction TB
        subgraph ROOT_SERVICES["Root-Level Services (43 files)"]
            DATA_SVC["document, chunk, citation,<br/>matter, timeline, library,<br/>bounding_box, summary"]
            INFRA_SVC["distributed_lock, pubsub,<br/>storage, email, notification,<br/>audit, eta_calculator, job_recovery,<br/>llm_error_handler"]
            ANALYTICS_SVC["anomaly, activity, dashboard_stats,<br/>tab_stats, queue_metrics, consistency"]
            DOMAIN_SVC["act_cache, cross_engine, global_search,<br/>matter_cost, reasoning_trace,<br/>reasoning_archive, summary_edit,<br/>summary_verification, section_index,<br/>ocr_chunk, ocr_result_merger,<br/>pdf_chunker, pdf_router,<br/>chunk_cleanup, chunk_recovery,<br/>chunk_bbox_linker, merge_trigger,<br/>contradiction_list, timeline_cache"]
        end
        subgraph SUB_PACKAGES["Subpackages (16 directories)"]
            RAG_SVC["rag/<br/>embedder, embedder_factory,<br/>voyage_embedder, voyage_reranker,<br/>hybrid_search, pipeline_service,<br/>query_rewriter, namespace,<br/>embedding_migration,<br/>reranker, reranker_base, reranker_factory"]
            CHUNK_PROC["chunking/<br/>text_splitter, parent_child_chunker,<br/>bbox_linker, spatial_text_mapper,<br/>token_counter"]
            OCR_SVC["ocr/<br/>processor, confidence_calculator,<br/>pattern_corrector, bbox_extractor,<br/>gemini_validator, human_review_service,<br/>validation_extractor"]
            MIG_SVC["mig/<br/>extractor, entity_resolver,<br/>graph, alias_prompts,<br/>correction_learning, prompts"]
            CONTRA_SVC["contradiction/<br/>comparator, statement_query"]
            SAFETY_SVC["safety/<br/>guardrail, language_police,<br/>quote_detector, subtle_detector,<br/>safety_guard, patterns, prompts"]
            EXPORT_SVC["export/<br/>pdf_generator, docx_generator,<br/>pptx_generator, court_certification,<br/>executive_summary_pdf,<br/>executive_summary_service,<br/>export_service"]
            EVAL_SVC["evaluation/<br/>ragas_evaluator, ab_testing,<br/>golden_dataset, baseline_service,<br/>regression_detector, models"]
            MEM_SVC["memory/<br/>redis_client, redis_keys,<br/>query_cache, query_cache_service,<br/>query_normalizer, session,<br/>matter, matter_service, summarizer"]
            JOB_SVC["job_tracking/<br/>tracker, chunk_progress,<br/>partial_progress, time_estimator"]
            TABLE_SVC["table_extraction/<br/>docling_provider, layout_extractor,<br/>extractor, formatter, models"]
            SECURITY_SVC["security/<br/>injection_detector"]
            VERIFY_SVC["verification/<br/>export_eligibility,<br/>verification_service"]
            INSPECT_SVC["inspector/<br/>inspector_service"]
            EMAIL_PKG["email/<br/>templates/processing_complete"]
            SUPA_SVC["supabase/<br/>client"]
        end
    end

    subgraph ENGINE_LAYER["Engines Layer (app/engines/) — 42 modules"]
        direction TB
        CITATION_ENG["citation/<br/>extractor, discovery, verifier,<br/>india_code, abbreviations,<br/>act_indexer, storage, validation,<br/>prompts, verification_prompts"]
        CONTRA_ENG["contradiction/<br/>classifier, comparator, scorer,<br/>prompts, statement_query"]
        TIMELINE_ENG["timeline/<br/>date_extractor, timeline_builder,<br/>anomaly_detector, entity_linker,<br/>event_classifier, legal_sequences,<br/>classification_prompts, prompts"]
        RAG_ENG["rag/<br/>generator, query_profile, prompts"]
        SUMMARY_ENG["summary/<br/>prompts"]
        ORCH_ENG["orchestrator/<br/>orchestrator, intent_analyzer,<br/>planner, executor, aggregator,<br/>adapters, audit_logger, models,<br/>query_history, streaming, prompts"]
    end

    subgraph WORKER_LAYER["Workers Layer (app/workers/tasks/) — 16 task files"]
        direction TB
        W_DOC["document_tasks<br/>process, validate, chunk,<br/>embed, extract_entities"]
        W_CHUNKED["chunked_document_tasks<br/>parallel processing >30pg"]
        W_ENGINE["engine_tasks<br/>citations, contradictions,<br/>dates, timeline"]
        W_SUMMARY["summary_tasks<br/>generate, verify"]
        W_TABLE["table_extraction_tasks"]
        W_VERIFY["verification_tasks"]
        W_EMBED["embedding_migration_tasks<br/>voyage_embedding_tasks"]
        W_LIBRARY["library_tasks"]
        W_MAINT["maintenance_tasks"]
        W_CHAINS["pipeline_chains<br/>task ordering"]
        W_ACT["act_validation_tasks"]
        W_EMAIL["email_tasks"]
        W_EVAL["evaluation_tasks"]
        W_QUOTA["quota_monitoring_tasks"]
        W_REASON["reasoning_archive_tasks"]
    end

    subgraph MODELS_LAYER["Models Layer (app/models/) — 39 Pydantic schemas"]
        direction TB
        M_CORE["Core: auth, matter, document,<br/>chunk, entity, citation,<br/>timeline, summary, search,<br/>chat, contradiction"]
        M_ANALYSIS["Analysis: anomaly, contradiction_list,<br/>consistency_issue, cross_engine,<br/>evaluation, inspector, orchestrator"]
        M_OPS["Operations: activity, cost, export,<br/>job, library, memory, notification,<br/>queue_status, quota, reasoning_trace,<br/>rerank, safety, tab_stats,<br/>table, verification, global_search"]
        M_OCR["OCR: ocr, ocr_chunk,<br/>ocr_confidence, ocr_validation"]
    end

    API_LAYER --> SERVICE_LAYER
    API_LAYER --> CORE_LAYER
    SERVICE_LAYER --> ENGINE_LAYER
    WORKER_LAYER --> SERVICE_LAYER
    WORKER_LAYER --> ENGINE_LAYER
    WORKER_LAYER --> CORE_LAYER
    API_LAYER --> MODELS_LAYER
    SERVICE_LAYER --> MODELS_LAYER

    style API_LAYER fill:#e3f2fd,stroke:#1976D2
    style CORE_LAYER fill:#f3e5f5,stroke:#7B1FA2
    style SERVICE_LAYER fill:#e8f5e9,stroke:#388E3C
    style ENGINE_LAYER fill:#fff8e1,stroke:#F9A825
    style WORKER_LAYER fill:#fbe9e7,stroke:#D84315
    style MODELS_LAYER fill:#f1f8e9,stroke:#689F38
```

---

## 3. Document Processing Pipeline

### 3a. Small Documents (< 30 pages) — Celery Chain

```mermaid
graph LR
    UPLOAD["API: Upload PDF"]
    PROC["process_document<br/>(Google Doc AI OCR)"]
    VAL["validate_ocr<br/>(Gemini check)"]
    CONF["calculate_confidence<br/>(scoring)"]
    CHUNK["chunk_document<br/>(text_splitter +<br/>parent_child_chunker)"]
    EMBED["embed_chunks<br/>(OpenAI / Voyage)"]
    ENTITY["extract_entities<br/>(GPT-4o)"]
    ALIAS["resolve_aliases<br/>(entity dedup)"]

    subgraph PARALLEL["Dispatched in Parallel"]
        CIT["extract_citations<br/>(citation engine)"]
        CONTRA["detect_contradictions<br/>(contradiction engine)"]
        DATES["extract_dates<br/>(timeline engine)"]
    end

    TABLE["extract_tables<br/>(Docling — triggered<br/>if layout blocks found)"]
    ACT_VAL["act_validation<br/>(verify cited acts)"]
    SUMMARY["generate_summary<br/>(GPT-4o)"]

    UPLOAD --> PROC --> VAL --> CONF --> CHUNK --> EMBED --> ENTITY --> ALIAS
    ALIAS --> CIT
    ALIAS --> CONTRA
    ALIAS --> DATES
    CHUNK -.->|"async"| TABLE
    CIT --> CONTRA
    CIT --> ACT_VAL
    DATES -.->|"after all docs"| SUMMARY

    style UPLOAD fill:#e3f2fd,stroke:#1976D2
    style PARALLEL fill:#fff3e0,stroke:#FF9800
    style TABLE fill:#f3e5f5,stroke:#7B1FA2
    style SUMMARY fill:#e8f5e9,stroke:#388E3C
```

### 3b. Large Documents (> 30 pages) — Chunked Parallel Processing

```mermaid
graph TB
    UPLOAD2["API: Upload PDF (>30 pages)"]
    DETECT["process_document<br/>detects >30 pages"]
    CHUNKED["process_document_chunked"]

    subgraph PARALLEL_OCR["Parallel OCR (page batches)"]
        B1["Batch 1<br/>pages 1-30"]
        B2["Batch 2<br/>pages 31-60"]
        BN["Batch N<br/>pages ..."]
    end

    TRACK["document_ocr_chunks table<br/>tracks each batch status"]
    VALIDATE["validate_ocr<br/>(Gemini check per batch)"]
    FINALIZE["finalize_chunked_document<br/>(merge OCR results)"]

    subgraph RECOVERY["Recovery Mechanism"]
        IDEMPOTENT["Idempotency check:<br/>if OCR_COMPLETE but 0 chunks<br/>→ trigger recovery"]
    end

    subgraph DOWNSTREAM["Downstream Pipeline"]
        CHUNK2["chunk_document"]
        EMBED2["embed_chunks"]
        ENTITY2["extract_entities"]
        ALIAS2["resolve_aliases"]
        CIT2["extract_citations"]
        CONTRA2["detect_contradictions"]
        DATES2["extract_dates"]
    end

    UPLOAD2 --> DETECT --> CHUNKED
    CHUNKED --> B1 & B2 & BN
    B1 & B2 & BN --> TRACK
    TRACK --> VALIDATE --> FINALIZE
    FINALIZE --> RECOVERY
    FINALIZE --> CHUNK2 --> EMBED2 --> ENTITY2 --> ALIAS2
    ALIAS2 --> CIT2 & DATES2
    CIT2 --> CONTRA2

    style UPLOAD2 fill:#e3f2fd,stroke:#1976D2
    style PARALLEL_OCR fill:#fce4ec,stroke:#E91E63
    style DOWNSTREAM fill:#e8f5e9,stroke:#388E3C
    style RECOVERY fill:#fff3e0,stroke:#FF9800
```

---

## 4. Frontend Architecture

### 4a. Page Routes & Navigation

```mermaid
graph TB
    ROOT["/ (Root Layout)<br/>providers.tsx"]

    subgraph AUTH_GROUP["(auth) Group"]
        LOGIN["/login"]
        SIGNUP["/signup"]
        FORGOT["/forgot-password"]
        RESET["/reset-password"]
    end

    subgraph LANDING_GROUP["(landing) Group"]
        LANDING["/ (Landing Page)"]
    end

    subgraph DASH_GROUP["(dashboard) Group"]
        DASH["/dashboard"]
        UPLOAD_PAGE["/upload"]
        UPLOAD_PROC["/upload/processing"]
        ACTIVITY["/activity"]
        ADMIN["/admin"]
        ADMIN_USAGE["/admin/usage"]
        USAGE["/usage"]
        TEST_API["/test-api-request"]
    end

    subgraph MATTER_GROUP["(matter) Group — /matter/[matterId]"]
        MATTER_ROOT["/matter/[matterId] (root)"]
        SUMMARY_TAB["/summary (default)"]
        TIMELINE_TAB["/timeline"]
        CITATIONS_TAB["/citations"]
        ENTITIES_TAB["/entities"]
        CONTRA_TAB["/contradictions"]
        DOCS_TAB["/documents"]
        VERIFY_TAB["/verification"]
    end

    OTHER_ROUTES["/settings, /inspector,<br/>/auth/callback"]

    ROOT --> AUTH_GROUP
    ROOT --> LANDING_GROUP
    ROOT --> DASH_GROUP
    ROOT --> MATTER_GROUP
    ROOT --> OTHER_ROUTES

    style AUTH_GROUP fill:#fce4ec,stroke:#E91E63
    style LANDING_GROUP fill:#e8f5e9,stroke:#4CAF50
    style DASH_GROUP fill:#e3f2fd,stroke:#1976D2
    style MATTER_GROUP fill:#fff3e0,stroke:#FF9800
```

### 4b. State Management & Data Flow

```mermaid
graph TB
    subgraph ZUSTAND["Zustand Stores (17)"]
        MS["matterStore<br/>current matter + workspace"]
        CS["chatStore<br/>Q&A conversations"]
        WS_STORE["workspaceStore<br/>active tab"]
        US["uploadStore +<br/>uploadWizardStore"]
        PS["processingStore +<br/>backgroundProcessingStore"]
        VS["verificationStore"]
        NS["notificationStore"]
        QAS["qaPanelStore"]
        SPLITS["splitViewStore +<br/>pdfSplitViewStore"]
        OTHERS["modelStore, libraryStore,<br/>featureStore, inspectorStore,<br/>activityStore"]
    end

    subgraph HOOKS["Custom Hooks (42)"]
        AUTH_HOOK["Auth: useAuth, useSession"]
        DATA_HOOKS["Data: useMatterSummary, useCitations,<br/>useEntities, useTimeline,<br/>useContradictions, useDocuments,<br/>useBoundingBoxes, useLiveDiscoveries"]
        REALTIME["Realtime: useSSE, useWebSocket"]
        ADMIN_HOOKS["Admin: useAdminStatus, useLLMQuota,<br/>useQueueStatus, useUsageDashboard,<br/>useUsageSummary, useServiceHealth"]
        MONITORING_HOOKS["Monitoring: useProcessingStatus,<br/>useDocumentStatus, useChunkMetrics,<br/>useQualityMetrics"]
        SEARCH_HOOKS["Search: useActDiscovery,<br/>useCrossEngine, useAnomalies"]
        VERIFY_HOOKS["Verification: useSummaryVerification,<br/>useVerificationActions,<br/>useVerificationQueue,<br/>useVerificationStats"]
        EXPORT_HOOKS["Export: useExportBuilder,<br/>useExportGeneration"]
        COST_HOOKS["Cost: useMatterCosts"]
        UI_HOOKS["UI: useSplitView, useCrossTabNavigation,<br/>useSummaryEdit, useUserPreferences,<br/>useUserProfile, useInspector"]
        FLAG_HOOKS["Feature: useFeatureSubscription,<br/>usePowerUserMode, useABTesting,<br/>useTimelineStats"]
    end

    subgraph API_CLIENT["API Client (lib/api/) — 34 modules"]
        CLIENT["client.ts<br/>Token injection + refresh<br/>30s timeout + error handling"]
        MODULES["chat, citations, documents,<br/>entities, matters, search,<br/>timeline, verifications,<br/>bounding-boxes, chunks,<br/>globalSearch, crossEngine"]
        ADMIN_MODULES["admin-monitoring, admin-pipeline,<br/>admin-queue, admin-quota,<br/>admin-usage, admin-maintenance"]
        OPS_MODULES["upload-orchestration, ab-testing,<br/>tabStats, costs, usage,<br/>evaluation, exports, jobs,<br/>library, notifications,<br/>activity, samples"]
    end

    subgraph EXTERNAL_STATE["External State"]
        SWR["SWR Cache<br/>HTTP-level caching"]
        SUPA_AUTH["Supabase Auth<br/>JWT session"]
        LS["localStorage<br/>preferences"]
    end

    ZUSTAND --> HOOKS
    HOOKS --> API_CLIENT
    API_CLIENT --> SWR
    API_CLIENT --> SUPA_AUTH
    ZUSTAND -.->|"persist"| LS

    style ZUSTAND fill:#e3f2fd,stroke:#1976D2
    style HOOKS fill:#f3e5f5,stroke:#7B1FA2
    style API_CLIENT fill:#fff3e0,stroke:#FF9800
    style EXTERNAL_STATE fill:#e8f5e9,stroke:#388E3C
```

### 4c. Matter Workspace Component Tree

```mermaid
graph TB
    LAYOUT["MatterWorkspaceWrapper"]
    HEADER["WorkspaceHeader<br/>Dashboard | Matter Name | Export | Share"]
    TABS["WorkspaceTabBar<br/>Summary | Timeline | Entities | Citations | ..."]
    CONTENT["WorkspaceContentArea"]
    QA["FloatingQAPanel / QAPanel<br/>ChatInput + StreamingResponse + Sources"]
    STATUS["ProcessingStatusBanner<br/>ServiceStatusBanner<br/>ConnectionStatusBanner"]

    subgraph TAB_CONTENT["Active Tab Content"]
        SUM["SummaryContent<br/>PartiesSection, KeyIssues,<br/>MatterStatistics, Verification"]
        TL["TimelineContent<br/>TimelineList, Horizontal, MultiTrack,<br/>AnomaliesBanner, EventCards"]
        CIT["CitationsContent<br/>ByAct, ByDocument,<br/>SplitViewModal, ActDiscovery"]
        ENT["EntitiesContent<br/>Graph, GridView, ListView,<br/>MergeSuggestions, DetailPanel"]
        CON["ContradictionsContent<br/>EntityGroups, StatementCards,<br/>Filters, Pagination"]
        DOC["DocumentsContent<br/>DocumentList, OCRQuality,<br/>AddDialog, ProcessingStatus"]
        VER["VerificationContent<br/>Queue, GroupedView,<br/>FindingDetailPanel, Stats"]
    end

    subgraph SHARED["Shared Components"]
        PDF["PdfViewerModal / PDFSplitView<br/>BboxOverlay"]
        EXPORT["ExportBuilder<br/>TemplateSelector,<br/>SectionList, Preview"]
        HELP["HelpButton / FeatureTour"]
    end

    subgraph EXTRA_AREAS["Additional Feature Areas (26 dirs)"]
        ONBOARD["onboarding/<br/>welcome, tours"]
        COSTS["costs/<br/>tracking, reports"]
        CROSS["crossEngine/<br/>search results"]
        SETTINGS["settings/<br/>appearance, preferences"]
        SUPPORT["support/<br/>help articles"]
        SYSTEM["system/<br/>status, error boundaries"]
        LIB["library/<br/>act management"]
        PROC["processing/<br/>progress indicators"]
        ADM["admin/<br/>monitoring dashboards"]
    end

    LAYOUT --> STATUS
    LAYOUT --> HEADER
    LAYOUT --> TABS
    LAYOUT --> CONTENT
    LAYOUT --> QA
    CONTENT --> TAB_CONTENT
    TAB_CONTENT -.-> SHARED
    TAB_CONTENT -.-> EXTRA_AREAS

    style LAYOUT fill:#e3f2fd,stroke:#1976D2
    style TAB_CONTENT fill:#fff3e0,stroke:#FF9800
    style SHARED fill:#f3e5f5,stroke:#7B1FA2
    style EXTRA_AREAS fill:#e8f5e9,stroke:#388E3C
```

---

## 5. Data Model (ER Diagram)

> **Full-detail version:** See [`docs/schema.dbml`](schema.dbml) — paste into [dbdiagram.io](https://dbdiagram.io) for an interactive, zoomable diagram with all columns, constraints, and ON DELETE behaviors.

```mermaid
erDiagram
    users ||--o{ matter_attorneys : "assigned to"
    users ||--o{ documents : "uploaded_by"
    users ||--o{ library_documents : "added_by"
    users ||--o{ alias_corrections : "corrected_by"
    users ||--o{ activities : "performed"
    users ||--o{ notifications : "receives"
    users ||--o{ exports : "created_by"
    users ||--o{ finding_verifications : "verified_by_user"
    users ||--|| user_preferences : "has preferences"

    matters ||--o{ matter_attorneys : "has members"
    matters ||--o{ documents : "contains"
    matters ||--o{ chunks : "contains"
    matters ||--o{ bounding_boxes : "contains"
    matters ||--o{ identity_nodes : "has entities"
    matters ||--o{ citations : "has citations"
    matters ||--o{ events : "has events"
    matters ||--o{ findings : "has findings"
    matters ||--o{ statement_comparisons : "has comparisons"
    matters ||--o{ processing_jobs : "has jobs"
    matters ||--o{ matter_memory : "has memory"
    matters ||--o{ act_resolutions : "has act refs"
    matters ||--o{ matter_library_links : "linked to library"
    matters ||--o{ document_ocr_chunks : "tracks OCR batches"
    matters ||--o{ anomalies : "has anomalies"
    matters ||--o{ alias_corrections : "has corrections"
    matters ||--o{ summary_verifications : "has summary checks"
    matters ||--o{ summary_notes : "has summary notes"
    matters ||--o{ summary_edits : "has summary edits"
    matters ||--o{ golden_dataset : "has test data"
    matters ||--o{ evaluation_results : "has evaluations"
    matters ||--o{ reasoning_traces : "has traces"
    matters ||--o{ exports : "has exports"
    matters ||--o{ ocr_human_review : "has OCR reviews"
    matters ||--o{ matter_query_history : "has query history"
    matters ||--o{ finding_verifications : "has finding checks"
    matters ||--o{ document_tables : "has extracted tables"
    matters ||--o{ section_index : "has section index"
    matters ||--o{ consistency_issues : "has consistency issues"
    matters ||--o{ ab_test_runs : "has A/B tests"

    documents ||--o{ chunks : "split into"
    documents ||--o{ bounding_boxes : "has bboxes"
    documents ||--o{ entity_mentions : "mentioned in"
    documents ||--o{ events : "source of"
    documents ||--o{ document_ocr_chunks : "split into OCR batches"
    documents ||--o{ ocr_validation_log : "validated"
    documents ||--o{ ocr_human_review : "reviewed"
    documents ||--o{ document_tables : "has tables"
    documents ||--o{ section_index : "has sections"
    documents ||--o{ toc_pages : "has TOC pages"

    chunks ||--o{ chunks : "parent_chunk_id"
    chunks ||--o{ entity_mentions : "chunk_id"

    identity_nodes ||--o{ identity_edges : "source_node"
    identity_nodes ||--o{ identity_edges : "target_node"
    identity_nodes ||--o{ entity_mentions : "entity_id"
    identity_nodes ||--o{ alias_corrections : "corrected entity"

    citations }o--|| documents : "source_document_id"
    citations }o--o| documents : "target_act_document_id"

    processing_jobs ||--o{ job_stage_history : "has stages"

    library_documents ||--o{ library_chunks : "split into"
    library_documents ||--o{ matter_library_links : "linked from"

    library_chunks ||--o{ library_chunks : "parent_chunk_id"

    findings ||--o{ reasoning_traces : "explained by"
    findings ||--o{ finding_verifications : "verified by"

    golden_dataset ||--o{ evaluation_results : "evaluated by"
    ab_test_runs }o--|| matters : "test matter_id"

    act_resolutions }o--o| act_validation_cache : "validated by cache"

    consistency_issues }o--o| documents : "issue document_id"

    bounding_boxes ||--o{ ocr_validation_log : "corrected bbox"

    llm_costs }o--o| matters : "cost matter_id"
    llm_costs }o--o| documents : "cost document_id"

    audit_logs }o--o| users : "audit user_id"
    audit_logs }o--o| matters : "audit matter_id"

    users {
        uuid id PK
        text email
        text full_name
    }

    matters {
        uuid id PK
        text title
        text description
        text status "active|archived|closed"
        text cause_title
    }

    matter_attorneys {
        uuid id PK
        uuid matter_id FK
        uuid user_id FK
        text role "owner|editor|viewer"
    }

    documents {
        uuid id PK
        uuid matter_id FK
        text filename
        text storage_path
        text document_type "case_file|act|annexure|other"
        text status "pending|processing|completed|failed"
        int page_count
    }

    chunks {
        uuid id PK
        uuid matter_id FK
        uuid document_id FK
        uuid parent_chunk_id FK
        int chunk_index
        text content
        vector embedding "vector(1536)"
        text chunk_type "parent|child|table"
        int page_number
        int token_count
        int text_start_offset
        int text_end_offset
    }

    bounding_boxes {
        uuid id PK
        uuid matter_id FK
        uuid document_id FK
        int page_number
        float x
        float y
        float width
        float height
        text text_content
        float confidence
    }

    identity_nodes {
        uuid id PK
        uuid matter_id FK
        text canonical_name
        text entity_type "person|organization|location|..."
        text_arr aliases
        int mention_count
    }

    identity_edges {
        uuid id PK
        uuid matter_id FK
        uuid source_node_id FK
        uuid target_node_id FK
        text relationship_type
        float confidence
    }

    entity_mentions {
        uuid id PK
        uuid entity_id FK
        uuid document_id FK
        uuid chunk_id FK
        int page_number
        text mention_text
        float confidence
    }

    citations {
        uuid id PK
        uuid matter_id FK
        uuid source_document_id FK
        uuid target_act_document_id FK
        text act_name
        text section
        text quoted_text
        int source_page
        text verification_status "verified|mismatch|not_found|pending"
        float confidence
    }

    events {
        uuid id PK
        uuid matter_id FK
        uuid document_id FK
        date event_date
        text event_date_precision "day|month|year|approximate"
        text event_type "filing|hearing|contract|..."
        text description
        float confidence
        boolean is_manual
    }

    findings {
        uuid id PK
        uuid matter_id FK
        text engine_type "citation|timeline|contradiction"
        text finding_type
        jsonb content
        float confidence
        text status "pending|verified|rejected"
    }

    statement_comparisons {
        uuid id PK
        uuid matter_id FK
        uuid entity_id
        uuid statement_a_id
        uuid statement_b_id
        text result "contradiction|consistent|uncertain"
        numeric confidence
        text contradiction_type
        text reasoning
    }

    processing_jobs {
        uuid id PK
        uuid matter_id FK
        uuid document_id FK
        text job_type
        text status "QUEUED|PROCESSING|COMPLETED|FAILED"
        text celery_task_id
        int progress_pct
    }

    job_stage_history {
        uuid id PK
        uuid job_id FK
        text stage_name
        text status
    }

    matter_memory {
        uuid id PK
        uuid matter_id FK
        text memory_type "query_history|timeline_cache|entity_graph|..."
        jsonb data
    }

    act_resolutions {
        uuid id PK
        uuid matter_id FK
        uuid act_document_id FK
        text act_name_normalized
        text resolution_status "available|missing|skipped"
        text user_action "uploaded|skipped|pending"
        int citation_count
    }

    library_documents {
        uuid id PK
        text filename
        text title
        text short_title
        text document_type "act|statute|judgment|..."
        int year
        text status "pending|processing|completed|failed"
    }

    library_chunks {
        uuid id PK
        uuid library_document_id FK
        uuid parent_chunk_id FK
        int chunk_index
        text content
        vector embedding "vector(1536)"
        text chunk_type "parent|child|table"
        int page_number
    }

    matter_library_links {
        uuid id PK
        uuid matter_id FK
        uuid library_document_id FK
        uuid linked_by FK
    }

    document_ocr_chunks {
        uuid id PK
        uuid matter_id FK
        uuid document_id FK
        int chunk_index
        int page_start
        int page_end
        text status "pending|processing|completed|failed"
        text ocr_full_text
    }

    anomalies {
        uuid id PK
        uuid matter_id FK
        text anomaly_type "gap|sequence_violation|duplicate|outlier"
        text severity "low|medium|high|critical"
        text title
        text explanation
        float confidence
        boolean verified
        boolean dismissed
    }

    alias_corrections {
        uuid id PK
        uuid matter_id FK
        uuid entity_id FK
        text correction_type "add|remove|merge"
        text alias_name
        uuid corrected_by FK
        jsonb metadata "immutable audit record"
    }

    summary_verifications {
        uuid id PK
        uuid matter_id FK
        text section_type "parties|subject_matter|current_status|key_issue"
        text section_id
        text decision "verified|flagged"
        uuid verified_by FK
    }

    summary_notes {
        uuid id PK
        uuid matter_id FK
        text section_type "parties|subject_matter|current_status|key_issue"
        text section_id
        text text
        uuid created_by FK
    }

    summary_edits {
        uuid id PK
        uuid matter_id FK
        text section_type "parties|subject_matter|current_status|key_issue"
        text section_id
        text original_content
        text edited_content
        uuid edited_by FK
    }

    activities {
        uuid id PK
        uuid user_id FK
        uuid matter_id FK "nullable"
        text type "processing_complete|contradictions_found|..."
        text description
        boolean is_read
    }

    notifications {
        uuid id PK
        uuid user_id FK
        uuid matter_id FK "nullable"
        text type "success|info|warning|error|in_progress"
        text title
        text message
        text priority "high|medium|low"
        boolean is_read
    }

    golden_dataset {
        uuid id PK
        uuid matter_id FK
        text question
        text expected_answer
        uuid created_by FK
    }

    evaluation_results {
        uuid id PK
        uuid matter_id FK
        uuid golden_item_id FK
        text question
        text answer
        float overall_score
        float context_recall
        float faithfulness
        float answer_relevancy
        text triggered_by "manual|auto|batch"
        jsonb pipeline_config
    }

    llm_costs {
        uuid id PK
        uuid matter_id FK "nullable — ON DELETE SET NULL"
        uuid document_id FK "nullable"
        text provider
        text operation
        int input_tokens
        int output_tokens
        numeric total_cost_inr
        numeric total_cost_usd
        int duration_ms
    }

    audit_logs {
        uuid id PK "NO RLS — service role only"
        text event_type
        uuid user_id FK "nullable"
        uuid matter_id FK "nullable"
        text action
        text result "success|denied|error|blocked"
        text path
        text method
        jsonb details
    }

    reasoning_traces {
        uuid id PK "immutable once created"
        uuid matter_id FK
        uuid finding_id FK "nullable"
        text engine_type "citation|timeline|contradiction|rag|entity"
        text model_used
        text reasoning_text
        float confidence_score
        int tokens_used
        text archive_path "cold storage path"
    }

    exports {
        uuid id PK
        uuid matter_id FK
        text format "pdf|docx|pptx"
        text status "pending|processing|completed|failed"
        text file_path
        uuid created_by FK
        jsonb verification_summary
    }

    user_preferences {
        uuid user_id PK
        boolean email_notifications_processing
        boolean email_notifications_verification
        text theme "light|dark|system"
    }

    ocr_validation_log {
        uuid id PK "immutable 7-year audit trail"
        uuid document_id FK
        uuid bbox_id FK "nullable"
        text original_text
        text corrected_text
        text validation_type "pattern|gemini|human"
        text reasoning
    }

    ocr_human_review {
        uuid id PK
        uuid document_id FK
        uuid matter_id FK
        uuid bbox_id FK "nullable"
        int page_number
        text status "pending|completed|skipped"
        text corrected_text
        uuid reviewed_by FK
    }

    matter_query_history {
        uuid id PK "append-only forensic"
        uuid matter_id FK
        uuid query_id
        jsonb audit_data "full QueryAuditEntry"
    }

    finding_verifications {
        uuid id PK
        uuid matter_id FK
        uuid finding_id FK "nullable"
        text finding_type
        text decision "pending|approved|rejected|flagged"
        float confidence_before
        float confidence_after "nullable"
        uuid verified_by FK
        text notes
    }

    document_tables {
        uuid id PK
        uuid document_id FK
        uuid matter_id FK
        int table_index
        int page_number
        text markdown_content
        jsonb json_content
        int row_count
        int col_count
        float confidence
    }

    section_index {
        uuid id PK
        uuid document_id FK
        uuid matter_id FK
        text section_number
        int page_number
        float confidence
        boolean is_toc
        text section_title
    }

    toc_pages {
        uuid id PK
        uuid document_id FK
        int page_number
        float confidence
        text detected_via
    }

    act_validation_cache {
        uuid id PK "global — shared across matters"
        text act_name_normalized "unique"
        text act_name_canonical
        int act_year
        text india_code_url
        text validation_status "valid|invalid|state_act|not_on_indiacode|unknown"
    }

    llm_quota_limits {
        uuid id PK
        varchar provider "unique"
        bigint daily_token_limit
        bigint monthly_token_limit
        numeric daily_cost_limit_inr
        numeric monthly_cost_limit_inr
        int alert_threshold_pct
    }

    consistency_issues {
        uuid id PK
        uuid matter_id FK
        text issue_type "date_mismatch|entity_name_mismatch|amount_discrepancy|..."
        text severity "info|warning|error"
        text source_engine "timeline|entity|citation|contradiction|rag"
        text conflicting_engine
        text description
        uuid document_id FK "nullable"
        text status "open|reviewed|resolved|dismissed"
    }

    ab_test_runs {
        uuid id PK
        uuid matter_id FK
        text status "pending|running_control|running_treatment|comparing|completed|failed"
        text control_embedding "default openai"
        text treatment_embedding "default voyage"
        jsonb control_scores
        jsonb treatment_scores
        text decision "control_wins|treatment_wins|no_significant_difference"
        float decision_confidence
    }
```

---

## 6. API Routes Map

```mermaid
graph LR
    subgraph PUBLIC["Public"]
        HEALTH["/api/health"]
    end

    subgraph AUTH_ROUTES["Auth Required"]
        subgraph MATTER_SCOPED["Matter-Scoped (/matters/{id}/...)"]
            R_DOCS["documents"]
            R_CHUNKS["chunks"]
            R_SEARCH["search"]
            R_CHAT["chat"]
            R_CITATIONS["citations"]
            R_ENTITIES["entities"]
            R_TIMELINE["timeline"]
            R_ANOMALIES["anomalies"]
            R_CONTRA["contradictions"]
            R_FINDINGS["verifications"]
            R_SUMMARY["summary"]
            R_EXPORT["exports"]
            R_BBOX["bounding_boxes"]
            R_COSTS["costs"]
            R_CROSS["cross_engine"]
            R_INSPECTOR["inspector"]
            R_JOBS["jobs"]
            R_NOTIFY["notifications"]
            R_ACTIVITY["activity"]
            R_TABLES["tables"]
            R_LIBRARY["library"]
            R_EVAL["evaluation"]
            R_REASON["reasoning_traces"]
            R_OCRVAL["ocr_validation"]
        end

        subgraph GLOBAL["Global"]
            R_MATTERS["matters"]
            R_USERS["users"]
            R_SESSION["session"]
            R_GSEARCH["global_search"]
            R_USAGE["usage"]
            R_SAMPLES["samples"]
            R_ABTEST["ab_testing"]
            R_DASHBOARD["dashboard"]
        end

        subgraph ADMIN_ROUTES["Admin Only"]
            R_MONITOR["admin/monitoring"]
            R_MAINT["admin/maintenance"]
            R_PIPELINE["admin/pipeline"]
            R_QUOTA["admin/quota"]
        end

        subgraph REALTIME["Real-time"]
            R_WS["WebSocket<br/>/ws"]
            R_SSE["SSE<br/>(via chat streaming)"]
        end
    end

    style PUBLIC fill:#e8f5e9,stroke:#4CAF50
    style MATTER_SCOPED fill:#e3f2fd,stroke:#1976D2
    style GLOBAL fill:#fff3e0,stroke:#FF9800
    style ADMIN_ROUTES fill:#fce4ec,stroke:#E91E63
    style REALTIME fill:#f3e5f5,stroke:#7B1FA2
```

---

## 7. RAG Pipeline Detail

```mermaid
graph TB
    USER_Q["User Query"]
    QR["query_rewriter<br/>Optimize query"]
    QP["query_profile<br/>Analyze intent"]

    subgraph RETRIEVAL["Retrieval"]
        SEMANTIC["Semantic Search<br/>match_chunks() via pgvector"]
        BM25["BM25 Full-Text Search<br/>GIN tsvector index"]
        LIBRARY_SEARCH["Library Search<br/>match_library_chunks_for_matter()"]
        HYBRID["hybrid_search<br/>RRF Fusion"]
        NAMESPACE["Namespace Isolation<br/>filter_matter_id required"]
    end

    subgraph EMBEDDING["Embedding Layer"]
        EMB_FACTORY["embedder_factory<br/>provider selection"]
        OAI_EMB["OpenAI Embedder<br/>text-embedding-3-small"]
        VOY_EMB["voyage_embedder<br/>voyage-law-2"]
        EMB_MIG["embedding_migration<br/>batch re-embed across providers"]
    end

    subgraph RERANK["Reranking"]
        RERANKER["reranker_factory<br/>provider selection"]
        VOY_RR["Voyage Reranker"]
        COH_RR["Cohere Reranker"]
    end

    subgraph GENERATION["Generation"]
        CONTEXT["Build Context<br/>Parent chunk expansion"]
        SAFETY["Safety Guard<br/>injection_detector +<br/>language_police"]
        GEN["RAG Generator<br/>(GPT-4o / Gemini)"]
        STREAM["Streaming Response<br/>SSE to client"]
    end

    subgraph MEMORY["Context Memory"]
        SESSION_MEM["Session Memory<br/>Redis"]
        MATTER_MEM["Matter Memory<br/>matter_memory table"]
        Q_CACHE["Query Cache<br/>Redis"]
    end

    subgraph EVAL_LOOP["Evaluation Loop"]
        GOLDEN["Golden Dataset<br/>question + expected_answer"]
        RAGAS["RAGAS Evaluator<br/>recall, faithfulness, relevancy"]
        AB_TEST["A/B Testing<br/>compare configurations"]
        REGRESSION["Regression Detector<br/>score degradation alerts"]
    end

    USER_Q --> QR --> QP
    QP --> EMBEDDING
    EMB_FACTORY --> OAI_EMB & VOY_EMB
    EMBEDDING --> SEMANTIC & BM25 & LIBRARY_SEARCH
    NAMESPACE -.->|"enforced"| SEMANTIC
    SEMANTIC & BM25 & LIBRARY_SEARCH --> HYBRID
    HYBRID --> RERANKER
    RERANKER --> VOY_RR & COH_RR
    VOY_RR & COH_RR --> CONTEXT --> SAFETY --> GEN --> STREAM

    Q_CACHE -.->|"cache hit"| STREAM
    SESSION_MEM -.->|"conversation ctx"| GEN
    MATTER_MEM -.->|"persistent ctx"| GEN

    STREAM -.->|"log results"| GOLDEN
    GOLDEN --> RAGAS --> AB_TEST --> REGRESSION

    style RETRIEVAL fill:#e3f2fd,stroke:#1976D2
    style EMBEDDING fill:#e0f2f1,stroke:#00897B
    style RERANK fill:#fff3e0,stroke:#FF9800
    style GENERATION fill:#e8f5e9,stroke:#388E3C
    style MEMORY fill:#f3e5f5,stroke:#7B1FA2
    style EVAL_LOOP fill:#fce4ec,stroke:#E91E63
```

---

## 8. Security & Isolation Model

```mermaid
graph TB
    subgraph LAYER1["Layer 1: Row-Level Security (Supabase RLS)"]
        RLS["Every table has RLS policies<br/>Checks: user → matter_attorneys → matter_id"]
        NO_RLS["Exception: audit_logs — NO RLS<br/>service role only, immutable"]
    end

    subgraph LAYER2["Layer 2: Vector Namespace Isolation"]
        VNS["match_chunks() REQUIRES filter_matter_id<br/>Cannot search across matters"]
    end

    subgraph LAYER3["Layer 3: Application Layer"]
        APP["Service layer always filters by matter_id<br/>API deps.py validates matter access"]
        LOCK["distributed_lock service<br/>prevents concurrent mutations"]
    end

    subgraph LAYER4["Layer 4: Content Safety"]
        SAFETY2["injection_detector — SQL/prompt injection<br/>safety_guard + language_police — content filtering<br/>quote_detector — detect manipulated quotes<br/>subtle_detector — adversarial input detection"]
    end

    subgraph IMMUTABLE["Immutable Audit Tables"]
        IMM_AUDIT["audit_logs — security events"]
        IMM_OCR["ocr_validation_log — 7-year compliance"]
        IMM_QUERY["matter_query_history — forensic trail"]
        IMM_ALIAS["alias_corrections — correction audit"]
        IMM_REASON["reasoning_traces — LLM chain-of-thought"]
    end

    subgraph AUTH_FLOW["Authentication Flow"]
        JWT["Supabase JWT"]
        MW["Next.js Middleware<br/>Token refresh (5min threshold)"]
        API_AUTH["FastAPI deps.py<br/>Token validation"]
        WS_AUTH["WebSocket auth.py<br/>Token validation"]
    end

    LAYER1 --> LAYER2 --> LAYER3 --> LAYER4
    JWT --> MW --> API_AUTH
    JWT --> WS_AUTH

    style LAYER1 fill:#e8f5e9,stroke:#4CAF50
    style LAYER2 fill:#e3f2fd,stroke:#1976D2
    style LAYER3 fill:#fff3e0,stroke:#FF9800
    style LAYER4 fill:#fce4ec,stroke:#E91E63
    style IMMUTABLE fill:#efebe9,stroke:#795548
    style AUTH_FLOW fill:#f3e5f5,stroke:#7B1FA2
```
