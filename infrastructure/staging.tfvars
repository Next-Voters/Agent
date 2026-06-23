environment    = "staging"
mailgun_domain = "PLACEHOLDER.mailgun.org"
mailgun_sender = "Next Voters (staging) <noreply@PLACEHOLDER.mailgun.org>"
share_base_url = "https://staging.PLACEHOLDER.example"
# Secrets (Mailgun API key, OpenAI/Tavily/Together keys, Supabase URL+key) are
# NOT set here — set them in SSM out-of-band after apply (see infrastructure/ssm.tf).
