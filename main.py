import os
import yaml
import json
import logging
import time
from fastapi import FastAPI, HTTPException
from datetime import datetime
from openai import OpenAI
from github import Github

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


for var in ["OPENAI_API_KEY", "GIT_TOKEN"]:
    if not os.getenv(var):
        logger.error(f"{var} not set")
        raise ValueError(f"{var} not set")

app = FastAPI(title="Crew AI Bot API", description="API to run Crew AI Bot", version="1.0.0")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def research_topic(topic, current_year):
    if not topic or not topic.strip():
        raise ValueError("Topic cannot be empty")
    if not current_year.isdigit():
        raise ValueError("Current year must be a number")

    prompt = f"""
    Summarize key developments in {topic} for {current_year} in 8 short bullet points:
    - Recent innovations (1 sentence).
    - Current trends (1 sentence).
    - Key statistics (1 sentence).
    - Future predictions (1 sentence).
    - Practical applications (1 sentence).
    - Notable challenge (1 sentence).
    - Industry impact (1 sentence).
    - Emerging opportunity (1 sentence).
    Keep it concise, max 30 words per bullet.
    """
    start_time = time.time()
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7
        )
        content = response.choices[0].message.content.strip()
        if not content:
            raise ValueError("Empty OpenAI response")
        logger.info(f"Research took {time.time() - start_time:.2f} seconds")
        return content
    except Exception as e:
        logger.error(f"OpenAI error: {str(e)}")
        raise RuntimeError(f"Research failed: {str(e)}")

def write_blog_post(topic, research_output, author_name, author_picture_url, cover_image_url, current_date_iso):
    prompt = f"""
    Write a short blog post about {topic} in Markdown, using this research:
    {research_output}
    Start with this frontmatter (single quotes):
    
    ---
    title: '(Catchy title)'
    status: 'published'
    author:
      name: '{author_name}'
      picture: '{author_picture_url}'
    slug: '(URL-friendly title)'
    description: '(One-sentence summary)'
    coverImage: '{cover_image_url}'
    category: '{topic}'
    publishedAt: '{current_date_iso}'
    ---
    
    Content: 2-3 paragraphs, max 200 words total, no code blocks.
    """
    start_time = time.time()
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.7
        )
        content = response.choices[0].message.content.strip()
        if not content:
            raise ValueError("Empty OpenAI response")
        logger.info(f"Blog post took {time.time() - start_time:.2f} seconds")
        return content
    except Exception as e:
        logger.error(f"OpenAI error: {str(e)}")
        raise RuntimeError(f"Blog post failed: {str(e)}")

def git_push_callback(task_output):
    start_time = time.time()
    pat = os.getenv("GIT_TOKEN")
    if not pat:
        logger.error("GIT_TOKEN not set")
        raise ValueError("GIT_TOKEN not set")

    g = Github(pat)
    repo = g.get_repo("abdullahhsajid/bmd-portfolio")

    original_file = os.path.join(os.getcwd(), 'report.md')
    if not os.path.exists(original_file):
        logger.error(f"Report file missing: {original_file}")
        raise FileNotFoundError(f"Report file missing")

    with open(original_file, 'r') as f:
        content = f.read().strip()

    metadata = {}
    if content.startswith('---'):
        frontmatter_end = content.index('---', 3)
        frontmatter = content[3:frontmatter_end].strip()
        metadata = yaml.safe_load(frontmatter) or {}
    slug = metadata.get('slug', 'default-slug')
    new_filename = f"{slug}.md"

    try:
        repo.create_file(
            f"outstatic/content/blogs/{new_filename}",
            f"Add {new_filename}",
            content
        )
    except Exception as e:
        logger.error(f"Push failed: {str(e)}")
        raise RuntimeError(f"Push failed: {str(e)}")

    metadata_json = {"metadata": []}
    try:
        metadata_file = repo.get_contents("outstatic/content/metadata.json")
        metadata_json = json.loads(metadata_file.decoded_content.decode())
    except:
        logger.info("metadata.json not found")

    new_entry = {
        "category": metadata.get('category', 'Uncategorized'),
        "collection": "blogs",
        "coverImage": metadata.get('coverImage', ''),
        "description": metadata.get('description', ''),
        "publishedAt": metadata.get('publishedAt', ''),
        "slug": slug,
        "status": metadata.get('status', 'draft'),
        "title": metadata.get('title', 'Untitled'),
        "path": f"outstatic/content/blogs/{slug}.md",
        "author": {
            "name": metadata.get('author', {}).get('name', ''),
            "picture": metadata.get('author', {}).get('picture', '')
        },
        "__outstatic": {
            "path": f"outstatic/content/blogs/{slug}.md"
        }
    }
    metadata_json['metadata'].append(new_entry)

    try:
        if 'metadata_file' in locals():
            repo.update_file(
                "outstatic/content/metadata.json",
                "Update metadata",
                json.dumps(metadata_json, indent=2),
                metadata_file.sha
            )
        else:
            repo.create_file(
                "outstatic/content/metadata.json",
                "Create metadata",
                json.dumps(metadata_json, indent=2)
            )
    except Exception as e:
        logger.error(f"Metadata update failed: {str(e)}")
        raise RuntimeError(f"Metadata update failed: {str(e)}")

    logger.info(f"Git push took {time.time() - start_time:.2f} seconds")
    return "Successfully pushed blog post"

@app.get("/")
async def root():
    return {"message": "Crew AI Bot API is running"}

@app.post("/run-agent")
async def run_agent(inputs: dict):
    start_time = time.time()
    try:
        required_fields = ['topic', 'author_name', 'author_picture_url', 'cover_image_url']
        for field in required_fields:
            if field not in inputs or not inputs[field] or not str(inputs[field]).strip():
                raise ValueError(f"Missing field: {field}")

        current_datetime_iso = datetime.now().isoformat() + "Z"
        topic = inputs['topic'].strip()
        current_year = str(datetime.now().year)
        author_name = inputs['author_name']
        author_picture_url = inputs['author_picture_url']
        cover_image_url = inputs['cover_image_url']

        research_output = research_topic(topic, current_year)
        logger.info(f"Research output length: {len(research_output)} chars")

        blog_content = write_blog_post(
            topic, research_output, author_name, author_picture_url, cover_image_url, current_datetime_iso
        )
        logger.info(f"Blog content length: {len(blog_content)} chars")

        with open('report.md', 'w') as f:
            f.write(blog_content)
        logger.info(f"File write took {time.time() - start_time:.2f} seconds so far")

        result = git_push_callback(None)
        total_time = time.time() - start_time
        logger.info(f"Total execution took {total_time:.2f} seconds")
        return {"result": result, "execution_time": total_time}
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
