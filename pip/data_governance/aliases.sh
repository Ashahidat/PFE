#!/usr/bin/env bash
# Shell aliases for local dev (source this file).
#
# Usage (bash/zsh):
#   source /home/ashahi/PFE/pip/data_governance/aliases.sh

alias atlas-reset='(cd /home/ashahi/PFE/pip/data_governance && ./reset_atlas.sh)'
alias grafana-reset='(cd /home/ashahi/PFE/pip/data_governance && ./reset_grafana.sh)'

# Internal Atlas (write-capable, localhost only)
alias atlas-internal-start='(cd /home/ashahi/PFE && ./pip/data_governance/run_atlas_internal.sh)'
alias atlas-internal-stop='(cd /home/ashahi/PFE/pip/data_governance/apache-atlas-2.4.0/bin && ./atlas_stop.py)'

# Atlas UI read-only proxy (humans entrypoint)
alias atlas-ui-start='(cd /home/ashahi/PFE && ./pip/data_governance/run_nginx_atlas_readonly.sh)'
alias atlas-ui-stop='(cd /home/ashahi/PFE && ./pip/data_governance/stop_nginx_atlas_readonly.sh)'
alias atlas-check='(cd /home/ashahi/PFE && ./pip/data_governance/check_atlas_ports.sh)'

# Convenience: start/stop the whole stack
alias atlas-ro-start='(cd /home/ashahi/PFE && ./pip/data_governance/start_atlas_readonly_stack.sh)'
alias atlas-ro-stop='(cd /home/ashahi/PFE && ./pip/data_governance/stop_atlas_readonly_stack.sh)'

# Grafana read-only stack
# Browser entrypoint: http://localhost:8081/api/grafana/
# The backend still serves /api/grafana/ on port 8000 for internal routing.
alias grafana-start='(cd /home/ashahi/PFE && ./pip/data_governance/start_grafana_readonly_stack_bg.sh)'
alias grafana-start-now='(cd /home/ashahi/PFE && ./pip/data_governance/start_grafana_readonly_stack.sh)'
alias grafana-stop='(cd /home/ashahi/PFE && ./pip/data_governance/stop_grafana_readonly_stack.sh)'

# Legacy Grafana system service aliases are intentionally neutralized.
# The local repo stack is the supported path.
alias grafana-system-start='echo "Deprecated: use grafana-start (local stack)" >&2; false'
alias grafana-system-stop='echo "Deprecated: use grafana-stop (local stack)" >&2; false'
