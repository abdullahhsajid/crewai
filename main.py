import os
import yaml
import json
import logging
from fastapi import FastAPI, HTTPException
from datetime import datetime
from openai import OpenAI
from github import Github


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Verify environment variables
for var in ["OPENAI_API_KEY", "GIT_TOKEN"]:
    if not os.getenv(var):
        logger.error(f"{var} not set")
        raise ValueError(f"{var} not set")

app = FastAPI(title="Crew AI Bot API", description="API to run Crew AI Bot", version="1.0.0")

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def research_topic(topic, current_year):
    if not topic or not topic.strip():
        raise ValueError("Topic cannot be empty or blank")
    if not current_year.isdigit():
        raise ValueError("Current year must be a valid number")

    prompt = f"""
    You are an expert in {topic}. Summarize key developments in {topic} for {current_year} in 10 concise bullet points, focusing on:
    - Recent innovations.
    - Current trends.
    - Notable statistics.
    - Future predictions.
    - Practical applications.
    Keep each bullet point brief (1-2 sentences). Base insights on general knowledge up to {current_year}.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7
        )
        content = response.choices[0].message.content.strip()
        if not content:
            raise ValueError("Empty response from OpenAI API")
        return content
    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        raise RuntimeError(f"Failed to generate research output: {str(e)}")

def write_blog_post(topic, research_output, author_name, author_picture_url, cover_image_url, current_date_iso):
    prompt = f"""
    Using the research below, write a concise blog post about {topic} in Markdown format.
    Start with this frontmatter (use single quotes):
    
    ---
    title: '(Catchy title based on research)'
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
    
    The content should be engaging, 3-4 paragraphs, and directly follow the frontmatter without code blocks.
    
    Research:
    {research_output}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7
        )
        content = response.choices[0].message.content.strip()
        if not content:
            raise ValueError("Empty response from OpenAI API")
        return content
    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        raise RuntimeError(f"Failed to generate blog post: {str(e)}")

def git_push_callback(task_output):
    pat = os.getenv("GIT_TOKEN")
    if not pat:
        logger.error("GIT_TOKEN not set")
        raise ValueError("GIT_TOKEN not set")

    g = Github(pat)
    repo = g.get_repo("abdullahhsajid/bmd-portfolio")

    original_file = os.path.join(os.getcwd(), 'report.md')
    if not os.path.exists(original_file):
        logger.error(f"Report file missing: {original_file}")
        raise FileNotFoundError(f"Report file missing: {original_file}")

    with open(original_file, 'r') as f:
        content = f.read().strip()

    # Process frontmatter
    metadata = {}
    if content.startswith('---'):
        frontmatter_end = content.index('---', 3)
        frontmatter = content[3:frontmatter_end].strip()
        metadata = yaml.safe_load(frontmatter)
        slug = metadata.get('slug', 'default-slug')
    else:
        slug = 'default-slug'

    new_filename = f"{slug}.md"

    # Push blog post
    try:
        repo.create_file(
            f"outstatic/content/blogs/{new_filename}",
            f"Add {new_filename}",
            content
        )
    except Exception as e:
        logger.error(f"Failed to push blog post: {str(e)}")
        raise RuntimeError(f"Failed to push blog post: {str(e)}")

    # Update metadata.json
    metadata_json = {"metadata": []}
    try:
        metadata_file = repo.get_contents("outstatic/content/metadata.json")
        metadata_json = json.loads(metadata_file.decoded_content.decode())
    except:
        logger.info("metadata.json not found, creating new")

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
                "Update metadata.json",
                json.dumps(metadata_json, indent=2),
                metadata_file.sha
            )
        else:
            repo.create_file(
                "outstatic/content/metadata.json",
                "Create metadata.json",
                json.dumps(metadata_json, indent=2)
            )
    except Exception as e:
        logger.error(f"Failed to update metadata.json: {str(e)}")
        raise RuntimeError(f"Failed to update metadata.json: {str(e)}")

    return "Successfully pushed blog post"

@app.get("/")
async def root():
    return {"message": "Crew AI Bot API is running"}

@app.post("/run-agent")
async def run_agent(inputs: dict):
    try:
        # Validate inputs
        required_fields = ['topic', 'author_name', 'author_picture_url', 'cover_image_url']
        for field in required_fields:
            if field not in inputs or not inputs[field] or not str(inputs[field]).strip():
                raise ValueError(f"Missing or empty field: {field}")

        current_datetime_iso = datetime.now().isoformat() + "Z"
        topic = inputs['topic'].strip()
        current_year = str(datetime.now().year)
        author_name = inputs['author_name']
        author_picture_url = inputs['author_picture_url']
        cover_image_url = inputs['cover_image_url']

        # Perform research
        research_output = research_topic(topic, current_year)
        logger.info(f"Research output length: {len(research_output)} chars")

        # Write blog post
        blog_content = write_blog_post(
            topic, research_output, author_name, author_picture_url, cover_image_url, current_datetime_iso
        )
        logger.info(f"Blog content length: {len(blog_content)} chars")

        # Save to report.md
        with open('report.md', 'w') as f:
            f.write(blog_content)

        # Push to GitHub
        result = git_push_callback(None)
        return {"result": result}
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
