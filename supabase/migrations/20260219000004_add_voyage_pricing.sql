-- Add Voyage AI provider pricing to llm_pricing table
-- These providers were added to PROVIDER_PRICING in code but not to the DB

INSERT INTO public.llm_pricing (provider, input_cost_per_1k, output_cost_per_1k, unit, notes)
SELECT v.provider, v.input_cost, v.output_cost, v.unit, v.notes
FROM (VALUES
    ('voyage-law-2',      0.00012000, 0.00000000, 'tokens',   'Voyage AI voyage-law-2 legal embeddings. $0.12 per 1M tokens.'),
    ('voyage-rerank-2.5', 0.00005000, 0.00000000, 'searches', 'Voyage AI rerank-2.5. $0.05 per 1M tokens.')
) AS v(provider, input_cost, output_cost, unit, notes)
WHERE NOT EXISTS (
    SELECT 1 FROM public.llm_pricing p
    WHERE p.provider = v.provider AND p.effective_to IS NULL
);
