FROM neo4j:5.20-community
ENV NEO4J_PLUGINS='["apoc", "gds"]'
ENV NEO4J_dbms_memory_heap_initial__size=1G
ENV NEO4J_dbms_memory_heap_max__size=2G
EXPOSE 7474 7687
