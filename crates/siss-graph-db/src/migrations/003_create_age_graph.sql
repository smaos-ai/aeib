-- SISS Knowledge Graph: Apache AGE Graph Setup
-- AGE provides Cypher query support for multi-hop graph traversals.
-- If AGE is not installed, this migration is a no-op (CREATE IF NOT EXISTS).

DO $$
BEGIN
    -- Attempt to load AGE extension
    CREATE EXTENSION IF NOT EXISTS age;
    -- Load AGE into the search path for this session
    SET search_path = ag_catalog, "$user", public;
    -- Create the SISS graph
    PERFORM create_graph('siss_graph');
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Apache AGE not available — skipping graph creation. ReBAC will use SQL fallback queries.';
END;
$$;
