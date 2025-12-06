#!/bin/bash
# Quick script to set up Grafana and view the dashboard

set -e

echo "🚀 Starting services..."
docker compose up -d

echo "⏳ Waiting for services to be healthy..."
sleep 15

echo "📊 Checking service status..."
docker compose ps

echo ""
echo "✅ Services are starting up!"
echo ""
echo "📈 To view Grafana dashboard:"
echo "   1. Open http://localhost:3000 in your browser"
echo "   2. Login with username: admin, password: admin"
echo "   3. The dashboard should auto-load, or go to Dashboards → ML Prediction API"
echo ""
echo "📊 Generating some traffic for metrics..."
python tests/load_test.py || echo "⚠️  Load test failed, but you can still access Grafana"

echo ""
echo "✨ Setup complete! Grafana should now be accessible at http://localhost:3000"
echo "   Dashboard will show metrics after traffic is generated."

