import os
import base64
import json
import yaml
import requests
from crewai import Agent, Task, Crew
from datetime import datetime
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv

load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_MODEL_NAME"] = os.getenv("OPENAI_MODEL_NAME")

app = FastAPI(title="Crew AI Bot API", description="API to run Crew AI Bot", version="1.0.0")

# GitHub configuration
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "abdullahhsajid")
GITHUB_REPO = os.getenv("GITHUB_REPO", "bmd-portfolio")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
GITHUB_TOKEN = os.getenv("GIT_TOKEN")

research_agent = Agent(
    role="{topic} Software Engineer Researcher",
    goal="Uncover cutting-edge developments in {topic}",
    backstory="""
        You're a cutting-edge research virtuoso with an uncanny talent for unearthing breakthrough discoveries in {topic}. 
    Renowned in digital circles for your exceptional ability to distill complex information into engaging, 
    shareable content that captivates readers from the first sentence. Your blog posts consistently trend
    because you blend authoritative expertise with an approachable voice that transforms industry insights into must-read digital experiences. 
    When readers need the definitive take on {topic}, your research-backed perspectives are what they share, cite, and trust.
    """
)

post_write_agent = Agent(
    role="Technical Blog Post Writer",
    goal="Craft engaging and informative blog posts in Markdown format.",
    backstory="""
        You are an expert technical writer skilled at transforming complex information
    into easily understandable and well-structured engaging blog content using Markdown.
    """
)

git_push_agent = Agent(
    role="Git Repository Manager",
    goal="Push blog posts to GitHub repository",
    backstory="""
        You are responsible for managing Git repositories and ensuring that blog posts 
        are properly pushed to the GitHub repository with appropriate metadata.
    """
)

task1 = Task(
    description="""
    Conduct a comprehensive investigation into {topic}, focusing specifically on:
        1. The latest breakthroughs and innovations since {current_year}
        2. Major trends reshaping this field in {current_year}
        3. Surprising statistics or data points that challenge conventional wisdom
        4. Expert predictions for future developments
        5. Practical applications or real-world impact stories
        
        Prioritize high-credibility sources and emerging research that hasn't yet reached mainstream awareness. Look beyond obvious information to uncover unique insights that would genuinely interest and surprise readers.
        
        Consider contrasting perspectives and identify any significant debates or controversies among experts in this domain during {current_year}.
        
        Ensure all findings are timely and relevant as of {current_year}, with particular emphasis on developments within the last 6 months.
    """,
    expected_output="A list with 10 bullet points of the most relevant information about {topic}",
    agent=research_agent
)

task2 = Task(
    description="""
    Based on the research provided, write a compelling and informative blog post should be attractive and engaging to readers.
    about {topic} in plain Markdown format. The blog post MUST start with the following
    frontmatter (using single quotes for string values) and MUST NOT be enclosed
    in any code blocks (do not use ```).

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

    The main content of the blog post should follow immediately after the closing '---' of the frontmatter, without any leading or trailing '```' or any other extra formatting that would treat it as a code block. The output should be directly usable as a .md file.

    Use the information provided in the research output to fill in the
    title, slug, description, category, and other relevant fields.
    Ensure the 'publishedAt' field uses the current date and time in ISO format (YYYY-MM-DDTHH:MM:SS.msZ).
    Strictly do not use any code blocks or delimiters in the output.
    """,
    expected_output="""A complete blog post in plain Markdown format, beginning with the specified frontmatter and followed directly by the blog content.
    Formatted as markdown without '```'""",
    agent=post_write_agent,
    output_file="report.md"  # Save the output to a file
)

def process_markdown_content(content):
    """Process markdown content and extract metadata."""
    cleaned_content = content.strip()
    
    # Remove markdown code block if present
    if cleaned_content.startswith('```markdown') or cleaned_content.startswith('```'):
        start_idx = cleaned_content.index('\n') + 1 if '\n' in cleaned_content else len(cleaned_content)
        end_idx = cleaned_content.rfind('```') if '```' in cleaned_content else len(cleaned_content)
        cleaned_content = cleaned_content[start_idx:end_idx].strip()
    
    # Extract metadata
    metadata = {}
    if cleaned_content.startswith('---'):
        second_delimiter = cleaned_content.find('---', 3)
        if second_delimiter != -1:
            frontmatter = cleaned_content[3:second_delimiter].strip()
            try:
                metadata = yaml.safe_load(frontmatter)
            except Exception as e:
                print(f"Error parsing frontmatter: {e}")
    
    return cleaned_content, metadata

def update_github_file(path, content, message):
    """Update or create a file in GitHub repository."""
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Check if file exists
    response = requests.get(url, headers=headers)
    
    data = {
        "message": message,
        "content": base64.b64encode(content.encode('utf-8')).decode('utf-8'),
        "branch": GITHUB_BRANCH
    }
    
    if response.status_code == 200:
        # File exists, need to include sha
        file_data = response.json()
        data["sha"] = file_data["sha"]
    
    # Create or update the file
    response = requests.put(url, headers=headers, json=data)
    
    if response.status_code not in [200, 201]:
        raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
    
    return response.json()

def update_metadata_json(metadata):
    """Update the metadata.json file in the GitHub repository."""
    metadata_path = "outstatic/content/metadata.json"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Try to get existing metadata.json
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{metadata_path}"
    response = requests.get(url, headers=headers)
    
    metadata_content = {"metadata": []}
    sha = None
    
    if response.status_code == 200:
        file_data = response.json()
        sha = file_data["sha"]
        content_encoded = file_data["content"]
        content_decoded = base64.b64decode(content_encoded).decode('utf-8')
        try:
            metadata_content = json.loads(content_decoded)
        except json.JSONDecodeError:
            # If metadata.json is invalid, we'll create a new one
            metadata_content = {"metadata": []}
    
    # Create new entry for the metadata
    slug = metadata.get('slug', 'default-slug')
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
            "path": f"outstatic/content/blogs/{slug}.md",
        }
    }
    
    # Add new entry to metadata
    metadata_content['metadata'].append(new_entry)
    
    # Update metadata.json
    data = {
        "message": f"Update metadata.json with {slug}",
        "content": base64.b64encode(json.dumps(metadata_content, indent=2).encode('utf-8')).decode('utf-8'),
        "branch": GITHUB_BRANCH
    }
    
    if sha:
        data["sha"] = sha
    
    response = requests.put(url, headers=headers, json=data)
    
    if response.status_code not in [200, 201]:
        raise Exception(f"GitHub API error updating metadata: {response.status_code} - {response.text}")
    
    return response.json()

task3 = Task(
    description="""
    Push the blog post to the GitHub repository and update the metadata.json file.
    The blog post is available in the file 'report.md'.
    """,
    expected_output="Confirmation that the blog post has been pushed to the repository",
    agent=git_push_agent
)

crew = Crew(
    agents=[research_agent, post_write_agent, git_push_agent],
    tasks=[task1, task2, task3],
    verbose=True
)

@app.get("/")
async def root():
    return {"message": "Crew AI Bot API is running"}

@app.post("/run-agent")
async def run_agent(inputs: dict):
    try:
        current_datetime_iso = datetime.now().isoformat() + "Z"
        crew_inputs = {
            "topic": inputs['topic'],
            "current_year": str(datetime.now().year),
            "current_date_iso": current_datetime_iso,
            "author_name": inputs['author_name'],
            "author_picture_url": inputs['author_picture_url'],
            "cover_image_url": inputs['cover_image_url'],
        }
        
        # Run the crew to generate the blog post
        result = crew.kickoff(inputs=crew_inputs)
        
        # Process the markdown content from the file
        with open("report.md", "r") as f:
            markdown_content = f.read()
        
        cleaned_content, metadata = process_markdown_content(markdown_content)
        
        # Push blog post to GitHub
        slug = metadata.get('slug', 'default-slug')
        blog_path = f"outstatic/content/blogs/{slug}.md"
        
        try:
            # Push the blog post to GitHub
            update_github_file(
                blog_path,
                cleaned_content,
                f"Add {slug}.md to blogs"
            )
            
            # Update metadata.json
            update_metadata_json(metadata)
            
            return {
                "result": result,
                "github_status": "success",
                "blog_url": f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/blob/{GITHUB_BRANCH}/{blog_path}"
            }
        except Exception as github_error:
            return {
                "result": result,
                "github_status": "error",
                "github_error": str(github_error)
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)