import os
from datetime import datetime
from fastapi import FastAPI, HTTPException


os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_MODEL_NAME"] = os.getenv("OPENAI_MODEL_NAME")

app = FastAPI(title="Crew AI Bot API", description="API to run Crew AI Bot", version="1.0.0")



# result = crew.kickoff(inputs=crew_inputs)

# print("############")
# print(result)

@app.get("/")
async def root():
    return {"message": "Crew AI Bot API is running"}

@app.post("/run-agent")
async def run_agent(inputs: dict):
    try:
        from crewai import Agent, Task, Crew

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
            agent=post_write_agent
        )
        
        crew = Crew(
            agents=[research_agent, post_write_agent],
            tasks=[task1, task2],
            verbose=True
        )
        current_datetime_iso = datetime.now().isoformat() + "Z"
        crew_inputs = {
            "topic": inputs['topic'],
            "current_year": str(datetime.now().year),
            "current_date_iso": current_datetime_iso,
            "author_name": inputs['author_name'],
            "author_picture_url": inputs['author_picture_url'],
            "cover_image_url": inputs['cover_image_url'],
        }
        result = crew.kickoff(inputs=crew_inputs)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
