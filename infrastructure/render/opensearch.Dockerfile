FROM opensearchproject/opensearch:2.14.0
ENV discovery.type=single-node
ENV bootstrap.memory_lock=true
ENV DISABLE_SECURITY_PLUGIN=true
ENV plugins.security.disabled=true
ENV OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g
EXPOSE 9200 9600
