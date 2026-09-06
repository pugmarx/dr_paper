import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const SUPABASE_URL = Deno.env.get('SUPABASE_URL') ?? ''
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
const MODERATION_TOKEN = Deno.env.get('MODERATION_TOKEN') ?? ''

Deno.serve(async (req) => {
  const url = new URL(req.url)
  const arxivId = url.searchParams.get('id')
  const action = url.searchParams.get('action')
  const token = url.searchParams.get('token')

  // Basic security token check (if configured)
  if (MODERATION_TOKEN && token !== MODERATION_TOKEN) {
    return new Response('Unauthorized moderation request', { status: 401 })
  }

  if (!arxivId || !action) {
    return new Response('Missing required id or action parameter', { status: 400 })
  }

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
    db: { schema: 'dr_paper' }
  })

  let updatePayload = {}
  let actionTitle = ''
  let statusColor = '#15803d'

  if (action === 'pub') {
    updatePayload = { status: 'published', updated_at: new Date().toISOString() }
    actionTitle = 'Published to Dr. Paper'
  } else if (action === 'feat') {
    updatePayload = { status: 'published', is_featured: true, updated_at: new Date().toISOString() }
    actionTitle = 'Featured & Published to Dr. Paper'
  } else if (action === 'rej') {
    updatePayload = { status: 'rejected', updated_at: new Date().toISOString() }
    actionTitle = 'Rejected'
    statusColor = '#b91c1c'
  } else {
    return new Response('Invalid action parameter', { status: 400 })
  }

  const { data, error } = await supabase
    .from('papers')
    .update(updatePayload)
    .eq('arxiv_id', arxivId)
    .select('title')

  if (error) {
    return new Response(`Database error: ${error.message}`, { status: 500 })
  }

  const paperTitle = data && data.length > 0 ? data[0].title : arxivId

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${actionTitle}</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #fbfaf7;
      color: #1a1a1a;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
      padding: 1.5rem;
      box-sizing: border-box;
    }
    .card {
      background: #ffffff;
      border: 1px solid #e5e5e0;
      border-radius: 8px;
      padding: 2rem;
      max-width: 460px;
      width: 100%;
      box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    .status {
      font-size: 0.85rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: ${statusColor};
      margin: 0 0 0.5rem 0;
    }
    h2 {
      font-size: 1.25rem;
      line-height: 1.35;
      margin: 0 0 1rem 0;
      color: #111;
    }
    p {
      color: #666;
      font-size: 0.9rem;
      line-height: 1.5;
      margin: 0.25rem 0;
    }
    code {
      font-family: monospace;
      background: #f3f3f0;
      padding: 0.15rem 0.35rem;
      border-radius: 4px;
    }
    .footer {
      margin-top: 1.5rem;
      padding-top: 1rem;
      border-top: 1px solid #eee;
    }
    a {
      color: #1a1a1a;
      text-decoration: underline;
      font-weight: 500;
    }
  </style>
</head>
<body>
  <div class="card">
    <p class="status">${actionTitle}</p>
    <h2>${paperTitle}</h2>
    <p>arXiv: <code>${arxivId}</code></p>
    <div class="footer">
      <a href="https://huggingface.co/spaces/pugmarx/dr-paper" target="_blank">View Live Publication &rarr;</a>
    </div>
  </div>
</body>
</html>`

  return new Response(html, {
    headers: { 'Content-Type': 'text/html; charset=utf-8' }
  })
})
