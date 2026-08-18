{{/* Chart name, overridable. */}}
{{- define "air-gapped-mirror.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Fully qualified name used for every resource. If the release name already
contains the chart name we don't repeat it, so `helm install mirror` gives
plain `mirror` rather than `mirror-air-gapped-mirror`.
*/}}
{{- define "air-gapped-mirror.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "air-gapped-mirror.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/name: {{ include "air-gapped-mirror.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Selector labels for the long-running mirror pods -- must stay stable
across upgrades (they're immutable on an existing Deployment).

The `component: mirror` part matters: the Service selects on these, and
the sync job's pods carry `component: sync` instead. Without that split a
running sync pod would match the Service and start receiving client
traffic it can't serve.
*/}}
{{- define "air-gapped-mirror.selectorLabels" -}}
app.kubernetes.io/name: {{ include "air-gapped-mirror.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: mirror
{{- end -}}

{{/*
Build an image reference. Call with a dict of the root context and the
image's short name, e.g.
  {{ include "air-gapped-mirror.image" (dict "ctx" . "name" "git-daemon") }}
*/}}
{{- define "air-gapped-mirror.image" -}}
{{- $reg := .ctx.Values.image.registry -}}
{{- if $reg -}}
{{- printf "%s/air-gapped-mirror/%s:%s" (trimSuffix "/" $reg) .name .ctx.Values.image.tag -}}
{{- else -}}
{{- printf "air-gapped-mirror/%s:%s" .name .ctx.Values.image.tag -}}
{{- end -}}
{{- end -}}
