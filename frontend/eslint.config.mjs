import { defineConfig, globalIgnores } from "eslint/config"
import nextVitals from "eslint-config-next/core-web-vitals"
import nextTs from "eslint-config-next/typescript"

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  // Guard against circular imports re-entering the codebase (FE-023).
  // The `import` plugin + TS resolver are already provided by
  // eslint-config-next, so this only adds the rule. Type-only import cycles
  // are flagged too — break them by extracting shared types to a leaf module.
  {
    rules: {
      "import/no-cycle": ["error", { maxDepth: Infinity, ignoreExternal: true }],
    },
  },
])

export default eslintConfig
