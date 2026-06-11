/**
 * Matter Components
 *
 * Components for matter workspace and management.
 */

export { MatterWorkspaceWrapper } from './MatterWorkspaceWrapper';

// FE-ARCH-01: matter workspace convergence gate + shared error screen
export { MatterGate } from './MatterGate';
export { MatterErrorScreen } from './MatterErrorScreen';

// Story 10A.1: Workspace Shell Header components
export { WorkspaceHeader } from './WorkspaceHeader';
export { EditableMatterName } from './EditableMatterName';
export { ExportDropdown } from './ExportDropdown';
export { ShareDialog } from './ShareDialog';

// Story 10A.2: Tab Bar Navigation components
export { WorkspaceTabBar, TAB_CONFIG, DEFAULT_TAB, TAB_LABELS, TAB_EPIC_INFO } from './WorkspaceTabBar';
export type { TabId } from './WorkspaceTabBar';

// Story 10A.3: Content Area and Q&A Panel Integration
export { WorkspaceContentArea } from './WorkspaceContentArea';
