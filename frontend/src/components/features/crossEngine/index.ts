/**
 * Cross-Engine Components Index
 *
 * Gap 5-3: Cross-Engine Correlation Links
 * Story 5.4: Cross-Engine Consistency Checking
 */

// Cross-engine link components
export {
  CrossEngineLink,
  CrossEngineLinkGroup,
  CrossEngineButton,
  type CrossEngineLinkProps,
  type CrossEngineLinkGroupProps,
  type CrossEngineButtonProps,
} from './CrossEngineLinks';

// Consistency issue components (Story 5.4)
export {
  ConsistencyWarningBadge,
  ConsistencyStatusIndicator,
  type ConsistencyWarningBadgeProps,
  type ConsistencyStatusIndicatorProps,
} from './ConsistencyWarningBadge';

export {
  ConsistencyIssueList,
  type ConsistencyIssueListProps,
} from './ConsistencyIssueList';
