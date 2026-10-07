{{- define "elastic-small.name" -}}
{{- printf "%s-elastic" .Release.Name | trunc 50 | trimSuffix "-" -}}
{{- end -}}
{{- define "elastic-small.esImage" -}}
{{ .Values.elasticsearch.image.repository }}:{{ .Values.elasticsearch.image.tag }}{{ if .Values.elasticsearch.image.digest }}@{{ .Values.elasticsearch.image.digest }}{{ end }}
{{- end -}}
{{- define "elastic-small.kibanaImage" -}}
{{ .Values.kibana.image.repository }}:{{ .Values.kibana.image.tag }}{{ if .Values.kibana.image.digest }}@{{ .Values.kibana.image.digest }}{{ end }}
{{- end -}}
