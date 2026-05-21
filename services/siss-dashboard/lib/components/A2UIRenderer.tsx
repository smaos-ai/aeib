/// Phase 38: A2UI Renderer Component
/// Enforces 18-component A2UI limit (fail-closed)

import React from 'react';

export interface ProjectionMetadata {
  component_count: number;
  decoupled: boolean;
  version: string;
}

export interface ProjectionResolverResponse {
  workflow_id: string;
  layout: Record<string, unknown>;
  data_binding: Record<string, unknown>;
  metadata: ProjectionMetadata;
}

interface A2UIRendererProps {
  projection: ProjectionResolverResponse;
}

/// A2UI Rendering Engine with strict 18-component limit (fail-closed)
export const A2UIRenderer: React.FC<A2UIRendererProps> = ({ projection }) => {
  // Fail-closed: Reject if component count exceeds 18
  if (projection.metadata.component_count > 18) {
    throw new Error(`ComponentLimitExceeded: A2UI limit is 18, got ${projection.metadata.component_count}`);
  }

  // Fail-closed: Reject if layout and data are not decoupled
  if (!projection.metadata.decoupled) {
    throw new Error('DataLayoutCoupling: Layout and data_binding must be decoupled');
  }

  return (
    <div data-testid="a2ui-renderer" className="a2ui-projection">
      <div className="projection-metadata">
        <span className="component-count">{projection.metadata.component_count}</span>
        <span className="version">{projection.metadata.version}</span>
        <span className="workflow-id">{projection.workflow_id}</span>
      </div>
      <div className="projection-layout">
        {typeof projection.layout === 'object' && projection.layout !== null && (
          <div className="layout-structure">
            {JSON.stringify(projection.layout, null, 2)}
          </div>
        )}
      </div>
      <div className="data-binding">
        {typeof projection.data_binding === 'object' && projection.data_binding !== null && (
          <div className="binding-pointers">
            {JSON.stringify(projection.data_binding, null, 2)}
          </div>
        )}
      </div>
    </div>
  );
};

export default A2UIRenderer;
