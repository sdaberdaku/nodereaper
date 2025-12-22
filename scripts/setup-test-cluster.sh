#!/bin/bash

# Script to set up a local Kubernetes cluster for NodeReaper integration testing
# Uses kind (Kubernetes in Docker) to create a multi-node test cluster

set -e

CLUSTER_NAME="nodereaper-test"

echo "🚀 Setting up kind cluster for NodeReaper integration tests..."

# Check if kind is installed
if ! command -v kind &> /dev/null; then
    echo "❌ kind is not installed. Please install it first: https://kind.sigs.k8s.io/docs/user/quick-start/#installation"
    exit 1
fi

# Check if Docker is running
if ! docker ps &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if cluster already exists
if kind get clusters | grep -q "^$CLUSTER_NAME$"; then
    echo "⚠️  Cluster $CLUSTER_NAME already exists. Deleting..."
    kind delete cluster --name "$CLUSTER_NAME"
fi

# Create cluster with custom configuration
echo "🔧 Creating kind cluster with multi-node configuration..."
kind create cluster --name "$CLUSTER_NAME" --config tests/integration/kind-config.yaml

# Wait for cluster to be ready
echo "⏳ Waiting for cluster to be ready..."
kubectl wait --for=condition=Ready nodes --all --timeout=300s

echo "✅ Kind cluster created successfully!"
echo ""
echo "🎉 Cluster setup complete!"
echo ""
echo "📋 Cluster information:"
kubectl cluster-info
echo ""
echo "🏷️  Node labels:"
kubectl get nodes --show-labels
echo ""
echo "🧪 To run integration tests:"
echo "   make test-integration"
echo ""
echo "🗑️  To clean up the cluster:"
echo "   kind delete cluster --name $CLUSTER_NAME"
