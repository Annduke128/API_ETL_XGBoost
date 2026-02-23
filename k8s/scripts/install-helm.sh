#!/bin/bash
# Script cài đặt Helm 3

set -e

echo "====================================="
echo "Installing Helm 3"
echo "====================================="

# Cài đặt Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Thêm Helm repositories
echo "Adding Helm repositories..."

helm repo add stable https://charts.helm.sh/stable
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add longhorn https://charts.longhorn.io
helm repo add metallb https://metallb.github.io/metallb
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add apache-airflow https://airflow.apache.org
helm repo add cloudnative-pg https://cloudnative-pg.github.io/charts
helm repo update

echo "====================================="
echo "Helm 3 Installed!"
echo "====================================="
helm version
