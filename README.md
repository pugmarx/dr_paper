# Dr. Paper

A curated publication of top AI research papers from arXiv, Hugging Face Daily Papers, and Substack newsletters (Last Week in AI), with human-in-the-loop editorial governance and a static web dashboard backed by Supabase.

## Quick Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configure `.env`:
- `GEMINI_API_KEY`: Google AI Studio key (or `GROQ_API_KEY`)
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`: Supabase credentials
- `SUPABASE_SCHEMA`: `dr_paper`

## Database Setup

1. Run `supabase/schema.sql` in your Supabase SQL editor.
2. In Supabase Dashboard -> **Settings -> API -> Exposed Schemas**, add `dr_paper`.

## Editorial Workflow

1. **Weekly Ingestion** (fetches top candidate papers and stages as `draft` in Supabase):
   ```bash
   python src/pipeline.py --ingest --limit 10
   ```
2. **Review & Publish** (interactive terminal moderation):
   ```bash
   python src/pipeline.py --review
   ```
   *Options*: `[P]ublish`, `[F]eature & Publish`, `[R]eject`, `[E]dit Summary`, `[S]kip`.
   *(You can also moderate and edit summaries directly in the Supabase Table Editor).*

3. **Publish Single Paper by ID**:
   ```bash
   python src/pipeline.py --publish 2401.12345
   ```

4. **Local Dry Run & Preview**:
   ```bash
   python src/pipeline.py --dry-run
   python src/pipeline.py --local --limit 3
   ```

## Deployment (Hugging Face Static Space)

1. Create a Space on Hugging Face using the **Static** SDK.
2. Upload the contents of `docs/` to your Space repository.
3. Only papers with `status = 'published'` are displayed on the public site.
