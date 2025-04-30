import os
from typing import Dict, List, Annotated, TypedDict, Literal, Union
from enum import Enum
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
import json
import re
from dotenv import load_dotenv
import os

load_dotenv()  # This loads variables from .env into environment

api_key = os.getenv("OPENAI_API_KEY") # Replace with your key
os.environ["OPENAI_API_KEY"] = api_key

BLOG_GRAPH = None
# State definition
class AgentState(TypedDict):
    messages: List[Union[SystemMessage, HumanMessage, AIMessage]]
    blog_topic: str
    outline: Dict
    sections: Dict
    current_section: str
    blog_post: str
    references: List[Dict]
    feedback: str
    status: str

# Define system prompts for different stages
SYSTEM_PROMPT_OUTLINE = """
You are an AI technical blog planning assistant. Your task is to create a detailed outline for a technical blog post.
Given a blog topic, create a comprehensive outline that includes:

1. A compelling title
2. A captivating introduction approach
3. 4-7 main sections with descriptive titles
4. Key points to cover in each section
5. A conclusion approach
6. 5-8 potential references and sources to cite

Format your response as a structured JSON object with these keys.
"""

SYSTEM_PROMPT_SECTION_WRITER = """
You are an expert technical writer with deep expertise in artificial intelligence, machine learning, and software development.
Your task is to write a section of a technical blog post. The writing should:

1. Reflect first-hand experience and deep expertise
2. Use a first-person perspective with occasional personal anecdotes
3. Include rich technical details beyond surface-level explanations
4. Incorporate code examples that are fully functional and well-commented
5. Reference specific sources, tools, and relevant research
6. Use analogies to explain complex concepts
7. Sound like it's written by a human expert practitioner

Write ONLY the specified section, not the entire blog post. Make this section detailed, informative and substantial.
"""

SYSTEM_PROMPT_REVIEWER = """
You are a technical blog editor focusing on quality and authenticity. Your task is to review a section of a technical blog post and provide specific feedback on:

1. Technical depth and accuracy
2. Authenticity of voice (does it sound like a real expert?)
3. Quality of explanations and analogies
4. Code quality and completeness
5. Proper citations and references
6. Coherence and flow

Provide specific, actionable feedback to improve the section. Be detailed and direct.
"""

SYSTEM_PROMPT_IMPROVER = """
You are an AI technical blog improvement specialist. Your task is to revise a section of a technical blog post based on specific feedback.

Incorporate ALL the feedback while maintaining:

1. The original expert voice and first-person perspective
2. Technical depth and accuracy
3. Real-world code examples that are properly explained
4. Clear explanations with analogies where appropriate
5. Proper references and citations
6. A human-written quality that feels authentic and authoritative

Make comprehensive improvements while ensuring the content maintains a personal, expert voice.
"""

SYSTEM_PROMPT_INTEGRATOR = """
You are an AI technical blog integration specialist. Your task is to assemble the individual sections of a blog post into a cohesive final draft.

As you integrate:

1. Ensure smooth transitions between sections
2. Maintain consistency in voice, tone, and perspective
3. Verify that references are properly cited and linked
4. Add any necessary connective elements between sections
5. Format the post properly with markdown headings, code blocks, etc.
6. Ensure the introduction properly sets up what follows and the conclusion effectively summarizes key points

The final draft should read as a unified, coherent piece written by a single expert author.
"""

# Node functions
def create_outline(state: AgentState) -> AgentState:
    """Create an outline for the blog post"""
    llm = ChatOpenAI(model="gpt-4", temperature=0.7)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT_OUTLINE),
        HumanMessage(content=f"Create a detailed outline for a technical blog post about: {state['blog_topic']}")
    ]
    
    response = llm.invoke(messages)
    
    # Extract JSON from the response
    try:
        json_match = re.search(r'```json\n(.*?)\n```', response.content, re.DOTALL)
        if json_match:
            outline_json = json.loads(json_match.group(1))
        else:
            # Try to find JSON without code blocks
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                outline_json = json.loads(json_match.group(0))
            else:
                # Last resort, try to parse the entire response
                outline_json = json.loads(response.content)
    except json.JSONDecodeError:
        # If JSON parsing fails, use the raw response
        outline_json = {"title": "Draft Title", "sections": {"introduction": "Introduction", "conclusion": "Conclusion"}}
    
    # Initialize sections dict with empty content
    # sections = {section: "" for section in outline_json.get("sections", {})}
    # sections["introduction"] = ""
    # sections["conclusion"] = ""

    sections_data = outline_json.get("sections", {})

    if isinstance(sections_data, dict):
    # Already a dict: keys are section names
        sections = {section: "" for section in sections_data}
    elif isinstance(sections_data, list):
    # List of dicts: convert to dict using 'title' as key
        sections = {section.get("title", f"Section {i+1}"): "" for i, section in enumerate(sections_data) if isinstance(section, dict)}
    else:
        sections = {}

    sections["introduction"] = ""
    sections["conclusion"] = ""
    
    return {
        **state,
        "outline": outline_json,
        "sections": sections,
        "current_section": "introduction",
        "status": "outline_created"
    }

def write_section(state: AgentState) -> AgentState:
    """Write a specific section of the blog post"""
    current_section = state["current_section"]
    outline = state["outline"]
    
    # Prepare context for the section
    section_context = ""
    if current_section == "introduction":
        section_context = f"""
        Write the introduction for a blog titled "{outline.get('title', 'Technical Blog')}".
        
        Approach: {outline.get('introduction_approach', 'Write a compelling introduction')}
        
        Key points from the outline:
        - Main topic: {state['blog_topic']}
        - The post will cover: {', '.join(outline.get('sections', {}).keys())}
        
        Write a detailed, engaging introduction from a first-person expert perspective.
        """
    elif current_section == "conclusion":
        section_context = f"""
        Write the conclusion for a blog titled "{outline.get('title', 'Technical Blog')}".
        
        Approach: {outline.get('conclusion_approach', 'Summarize key points and provide next steps')}
        
        The post covered these main sections:
        {', '.join(outline.get('sections', {}).keys())}
        
        Write a thoughtful conclusion that summarizes key points and provides actionable takeaways.
        """
    else:
        # For regular sections
        section_title = current_section
        section_points = outline.get("sections", {}).get(current_section, [])
        
        section_context = f"""
        Write the section titled "{section_title}" for the blog about "{state['blog_topic']}".
        
        Key points to cover in this section:
        {section_points}
        
        Include relevant code examples, personal insights, and references where appropriate.
        """
    
    llm = ChatOpenAI(model="gpt-4", temperature=0.7)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT_SECTION_WRITER),
        HumanMessage(content=section_context)
    ]
    
    response = llm.invoke(messages)
    
    # Update the section content
    sections = state["sections"].copy()
    sections[current_section] = response.content
    
    return {
        **state,
        "sections": sections,
        "status": f"section_{current_section}_written"
    }

def review_section(state: AgentState) -> AgentState:
    """Review the current section and provide feedback"""
    current_section = state["current_section"]
    section_content = state["sections"][current_section]
    
    llm = ChatOpenAI(model="gpt-4", temperature=0.7)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT_REVIEWER),
        HumanMessage(content=f"""
        Review this {current_section} section for a technical blog about {state['blog_topic']}.
        
        SECTION CONTENT:
        {section_content}
        
        Provide specific, actionable feedback to improve this section's quality, technical depth, authenticity, and overall effectiveness.
        """)
    ]
    
    response = llm.invoke(messages)
    
    return {
        **state,
        "feedback": response.content,
        "status": f"section_{current_section}_reviewed"
    }

def improve_section(state: AgentState) -> AgentState:
    """Improve the section based on feedback"""
    current_section = state["current_section"]
    section_content = state["sections"][current_section]
    feedback = state["feedback"]
    
    llm = ChatOpenAI(model="gpt-4", temperature=0.7)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT_IMPROVER),
        HumanMessage(content=f"""
        Improve this {current_section} section for a technical blog about {state['blog_topic']}.
        
        CURRENT CONTENT:
        {section_content}
        
        FEEDBACK:
        {feedback}
        
        Rewrite the section to address all feedback while maintaining an authentic expert voice and technical depth.
        """)
    ]
    
    response = llm.invoke(messages)
    
    # Update the improved section
    sections = state["sections"].copy()
    sections[current_section] = response.content
    
    return {
        **state,
        "sections": sections,
        "status": f"section_{current_section}_improved"
    }

def select_next_section(state: AgentState) -> AgentState:
    """Select the next section to work on or finish"""
    current_section = state["current_section"]
    outline = state["outline"]
    
    # Get all section names
    all_sections = ["introduction"] + list(outline.get("sections", {}).keys()) + ["conclusion"]
    
    # Find the index of the current section
    try:
        current_index = all_sections.index(current_section)
        # If there's a next section, select it
        if current_index < len(all_sections) - 1:
            next_section = all_sections[current_index + 1]
            return {
                **state,
                "current_section": next_section,
                "status": f"moving_to_{next_section}"
            }
        else:
            # If we've completed all sections, move to integration
            return {
                **state,
                "status": "ready_for_integration"
            }
    except ValueError:
        # If the current section isn't in the list (shouldn't happen), default to introduction
        return {
            **state,
            "current_section": "introduction",
            "status": "moving_to_introduction"
        }

def integrate_blog(state: AgentState) -> AgentState:
    """Integrate all sections into a cohesive blog post"""
    sections = state["sections"]
    outline = state["outline"]
    
    # Prepare the content for integration
    section_content = ""
    for section_name, content in sections.items():
        if section_name == "introduction":
            section_content += f"# {outline.get('title', 'Technical Blog')}\n\n{content}\n\n"
        elif section_name == "conclusion":
            section_content += f"## Conclusion\n\n{content}\n\n"
        else:
            section_content += f"## {section_name}\n\n{content}\n\n"
    
    llm = ChatOpenAI(model="gpt-4", temperature=0.7)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT_INTEGRATOR),
        HumanMessage(content=f"""
        Integrate these sections into a cohesive technical blog post about {state['blog_topic']}.
        
        SECTIONS TO INTEGRATE:
        {section_content}
        
        Create a final, polished blog post that flows naturally between sections and maintains a consistent expert voice throughout.
        """)
    ]
    
    response = llm.invoke(messages)
    
    return {
        **state,
        "blog_post": response.content,
        "status": "blog_completed"
    }

def should_continue_writing(state: AgentState) -> Literal["continue", "integrate"]:
    """Determine if we should continue writing sections or move to integration"""
    if state["status"] == "ready_for_integration":
        return "integrate"
    return "continue"

# Create the graph
def create_blog_generation_graph():
    """Create the LangGraph for blog generation"""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("create_outline", create_outline)
    workflow.add_node("write_section", write_section)
    workflow.add_node("review_section", review_section)
    workflow.add_node("improve_section", improve_section)
    workflow.add_node("select_next_section", select_next_section)
    workflow.add_node("integrate_blog", integrate_blog)
    
    # Add edges
    workflow.add_edge("create_outline", "write_section")
    workflow.add_edge("write_section", "review_section")
    workflow.add_edge("review_section", "improve_section")
    workflow.add_edge("improve_section", "select_next_section")
    
    # Conditional edge from select_next_section
    workflow.add_conditional_edges(
        "select_next_section",
        should_continue_writing,
        {
            "continue": "write_section",
            "integrate": "integrate_blog"
        }
    )
    
    workflow.add_edge("integrate_blog", END)
    
    # Set the entry point
    workflow.set_entry_point("create_outline")
    
    return workflow

BLOG_GRAPH = create_blog_generation_graph()  # <-- Assign to global
graph_runnable = BLOG_GRAPH.compile() 
# Function to run the graph
def generate_technical_blog(topic: str):
    global BLOG_GRAPH
    """Generate a complete technical blog on the given topic"""
    # Initialize the state
    initial_state = {
        "messages": [],
        "blog_topic": topic,
        "outline": {},
        "sections": {},
        "current_section": "",
        "blog_post": "",
        "references": [],
        "feedback": "",
        "status": "starting"
    }
    
    # Create and compile the graph

    
    # Execute the graph
    for output in graph_runnable.stream(initial_state):
        current_state = list(output.values())[0]
        print(f"Status: {current_state['status']}")
    
    # Return the final blog post
    return current_state["blog_post"]

# Example usage


if __name__ == "__main__":
    # Ask the user for the blog topic via command line input
    topic = input("Enter the technical blog topic: ")
    blog_post = generate_technical_blog(topic)
    
    # Save the output to a file
    with open("technical_blog.md", "w") as f:
        f.write(blog_post)
    
    print("Blog post generated and saved to technical_blog.md")