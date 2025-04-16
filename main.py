from openai import OpenAI
import os
from fastapi import FastAPI, HTTPException
from datetime import datetime
from dotenv import load_dotenv
import yaml
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_MODEL_NAME"] = os.getenv("MODEL", "gpt-4")

app = FastAPI(title="Crew AI Bot API", description="API to run Crew AI Bot", version="1.0.0")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def research_topic(topic, current_year):
    prompt = f"""
    Conduct a comprehensive investigation into {topic}, focusing specifically on:
    1. The latest breakthroughs and innovations since {current_year}
    2. Major trends reshaping this field in {current_year}
    3. Surprising statistics or data points that challenge conventional wisdom
    4. Expert predictions for future developments
    5. Practical applications or real-world impact stories
    
    Prioritize high-credibility sources and emerging research that hasn't yet reached mainstream awareness.
    Look beyond obvious information to uncover unique insights that would genuinely interest and surprise readers.
    Consider contrasting perspectives and identify significant debates or controversies among experts in {current_year}.
    Ensure all findings are timely and relevant as of {current_year}, with emphasis on developments within the last 6 months.
    
    Return a list with 10 bullet points of the most relevant information.
    """
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL_NAME"),
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000
    )
    return response.choices[0].message.content

def write_blog_post(topic, research_output, author_name, author_picture_url, cover_image_url, current_date_iso):
    prompt = f"""
    Based on the following research about {topic}, write a compelling and informative blog post in plain Markdown format.
    The blog post MUST start with the following frontmatter (using single quotes for string values) and MUST NOT be enclosed in code blocks:
    
    ---
    title: '(A catchy title based on the research)'
    status: 'published'
    author:
      name: '{author_name}'
      picture: '{author_picture_url}'
    slug: '(A URL-friendly version of the title)'
    description: '(A brief summary of the blog post)'
    coverImage: '{cover_image_url}'
    category: '(A relevant category for the topic)'
    publishedAt: '{current_date_iso}'
    ---
    
    The main content should follow immediately after the frontmatter, without code blocks.
    Use the research to fill in the title, slug, description, and category.
    
    Research:
    {research_output}
    """
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL_NAME"),
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000
    )
    return response.choices[0].message.content

# GitHub API for pushing files (avoids cloning)
from github import Github

def git_push_callback(task_output):
    pat = os.getenv("GIT_TOKEN")
    if not pat:
        logger.error("GIT_TOKEN environment variable is not set")
        raise ValueError("GIT_TOKEN environment variable is not set")

    g = Github(pat)
    repo = g.get_repo("abdullahhsajid/bmd-portfolio")

    original_file = os.path.join(os.getcwd(), 'report.md')
    if not os.path.exists(original_file):
        logger.error(f"Report file does not exist: {original_file}")
        raise FileNotFoundError(f"Report file does not exist: {original_file}")

    def process_file(file_path):
        with open(file_path, 'r') as f:
            content = f.read()

        cleaned_content = content.strip()
        if cleaned_content.startswith('```markdown') or cleaned_content.startswith('```'):
            start_idx = cleaned_content.index('\n') + 1 if '\n' in cleaned_content else len(cleaned_content)
            end_idx = cleaned_content.rfind('```') if '```' in cleaned_content else len(cleaned_content)
            cleaned_content = cleaned_content[start_idx:end_idx].strip()

        metadata = {}
        if cleaned_content.startswith('---'):
            frontmatter_end = cleaned_content.index('---', 3)
            frontmatter = cleaned_content[3:frontmatter_end].strip()
            metadata = yaml.safe_load(frontmatter)
            slug = metadata.get('slug', 'default-slug')
        else:
            slug = 'default-slug'

        with open(file_path, 'w') as f:
            f.write(cleaned_content)

        return slug, metadata, cleaned_content

    def update_metadata_json(metadata):
        metadata_json = {"metadata": []}
        try:
            metadata_file = repo.get_contents("outstatic/content/metadata.json")
            metadata_json = json.loads(metadata_file.decoded_content.decode())
        except:
            logger.info("metadata.json not found, creating new one")

        new_entry = {
            "category": metadata.get('category', 'Uncategorized'),
            "collection": "blogs",
            "coverImage": metadata.get('coverImage', ''),
            "description": metadata.get('description', ''),
            "publishedAt": metadata.get('publishedAt', ''),
            "slug": metadata.get('slug', 'default-slug'),
            "status": metadata.get('status', 'draft'),
            "title": metadata.get('title', 'Untitled'),
            "path": f"outstatic/content/blogs/{metadata.get('slug', 'default-slug')}.md",
            "author": {
                "name": metadata.get('author', {}).get('name', ''),
                "picture": metadata.get('author', {}).get('picture', '')
            },
            "__outstatic": {
                "path": f"outstatic/content/blogs/{metadata.get('slug', 'default-slug')}.md",
            }
        }
        metadata_json['metadata'].append(new_entry)

        try:
            repo.update_file(
                "outstatic/content/metadata.json",
                "Update metadata.json with new blog entry",
                json.dumps(metadata_json, indent=2),
                metadata_file.sha
            )
        except:
            repo.create_file(
                "outstatic/content/metadata.json",
                "Create metadata.json with new blog entry",
                json.dumps(metadata_json, indent=2)
            )

    slug, metadata, content = process_file(original_file)
    new_filename = f"{slug}.md"

    try:
        repo.create_file(
            f"outstatic/content/blogs/{new_filename}",
            f"Add {new_filename} to outstatic/content/blogs",
            content
        )
    except Exception as e:
        logger.error(f"Failed to push blog post: {str(e)}")
        raise RuntimeError(f"Failed to push blog post to repository: {str(e)}")

    update_metadata_json(metadata)

    return "Successfully pushed blog post to GitHub repository"

@app.get("/")
async def root():
    return {"message": "Crew AI Bot API is running"}

@app.post("/run-agent")
async def run_agent(inputs: dict):
    try:
        current_datetime_iso = datetime.now().isoformat() + "Z"
        topic = inputs['topic']
        current_year = str(datetime.now().year)
        author_name = inputs['author_name']
        author_picture_url = inputs['author_picture_url']
        cover_image_url = inputs['cover_image_url']

        # Perform research
        research_output = research_topic(topic, current_year)
        logger.info(f"Research output: {research_output}")

        # Write blog post
        blog_content = write_blog_post(
            topic, research_output, author_name, author_picture_url, cover_image_url, current_datetime_iso
        )
        logger.info(f"Blog content generated")

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
