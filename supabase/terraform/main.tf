terraform {
  required_providers {
    supabase = {
      source  = "supabase/supabase"
      version = "~> 1.0"
    }
  }
}

variable "supabase_access_token" {
  description = "Supabase Access Token"
  type        = string
  sensitive   = true
}

variable "organization_id" {
  description = "Supabase Organization ID"
  type        = string
}

provider "supabase" {
  access_token = var.supabase_access_token
}

resource "supabase_project" "production" {
  organization_id   = var.organization_id
  name              = "user-management-prod"
  database_password = "secure-database-password-change-me"
  region            = "us-east-1"
  
  # Enabling PITR requires Pro plan or higher in Supabase
  # PITR is managed at the project level
  # Configuration depends on the provider capabilities
  lifecycle {
    ignore_changes = [database_password]
  }
}

# Note: Automated daily backups and PITR for Supabase 
# are typically enabled via the Supabase Dashboard for the project,
# or through the Supabase Management API. 
# They are automatically enabled when upgrading to the Pro plan.
