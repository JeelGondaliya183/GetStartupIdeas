import streamlit as st
import requests
from bs4 import BeautifulSoup
from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain
import pandas as pd
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
import re
from urllib.parse import urljoin, urlparse

st.set_page_config(
    page_title="Startup Idea Finder",
    page_icon="💡",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_resource
def get_llm(model_name: str = "llama3.2"):
    """Initialize Ollama LLM with specified model"""
    try:
        return OllamaLLM(model=model_name)
    except Exception as e:
        st.error(f"Error initializing Ollama model '{model_name}': {str(e)}")
        return None

class WebScraper:
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def test_connection(self, url: str) -> bool:
        try:
            response = self.session.get(url, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def scrape_techcrunch_funding(self, num_articles: int = 10) -> List[Dict]:
        articles = []
        
        urls_to_try = [
            "https://techcrunch.com/category/startups/",
            "https://techcrunch.com/tag/funding/",
            "https://techcrunch.com/"
        ]
        
        for url in urls_to_try:
            try:
                st.write(f"Trying to scrape: {url}")
                
                if not self.test_connection(url):
                    st.write(f"Cannot connect to {url}")
                    continue
                
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                selectors_to_try = [
                    ('article', {'class': re.compile(r'post-block.*')}),
                    ('div', {'class': re.compile(r'post-.*')}),
                    ('article', {}),
                    ('div', {'class': re.compile(r'wp-block.*')}),
                    ('h2', {}),
                    ('h3', {}),
                ]
                
                for tag, attrs in selectors_to_try:
                    elements = soup.find_all(tag, attrs, limit=num_articles * 2)
                    
                    if elements:
                        st.write(f"Found {len(elements)} {tag} elements")
                        break
                
                if not elements:
                    st.write(f"No elements found with any selector on {url}")
                    continue
                
                for element in elements:
                    if len(articles) >= num_articles:
                        break
                    
                    try:
                        title_elem = None
                        link_elem = None
                        
                        # Strategy 1 direct h2/h3 with link
                        if element.name in ['h2', 'h3']:
                            title_elem = element
                            link_elem = element.find('a')
                        else:
                            # Strategy 2 find h2/h3 inside element
                            title_elem = element.find(['h2', 'h3'])
                            if title_elem:
                                link_elem = title_elem.find('a')
                            else:
                                # Strategy 3 find any link
                                link_elem = element.find('a')
                                if link_elem:
                                    title_elem = link_elem.parent
                        
                        if not title_elem or not link_elem:
                            continue
                        
                        title = title_elem.get_text().strip()
                        link = link_elem.get('href', '')
                        
                        if not title or not link:
                            continue
                        
                        if link.startswith('/'):
                            link = urljoin(url, link)
                        
                        funding_keywords = [
                            'raises', 'funding', 'series', 'million', 'billion', 
                            'investment', 'venture', 'seed', 'round', 'capital',
                            'valuation', 'startup', 'vc', 'investor'
                        ]
                        
                        if not any(keyword in title.lower() for keyword in funding_keywords):
                            continue
                        
                        excerpt = ""
                        excerpt_elem = element.find('p') or element.find('div', string=True)
                        if excerpt_elem:
                            excerpt = excerpt_elem.get_text().strip()[:200] + "..."
                        
                        date = ""
                        date_elem = element.find('time')
                        if date_elem:
                            date = date_elem.get('datetime', '') or date_elem.get_text().strip()
                        
                        article_data = {
                            'title': title,
                            'link': link,
                            'excerpt': excerpt,
                            'date': date,
                            'source': 'TechCrunch'
                        }
                        
                        if not any(a['link'] == link for a in articles):
                            articles.append(article_data)
                            st.write(f"Added: {title[:50]}...")
                        
                    except Exception as e:
                        continue
                
                if articles:
                    st.success(f"successfully scraped {len(articles)} articles from TechCrunch")
                    break
                else:
                    st.write(f"No funding articles found on {url}")
            
            except Exception as e:
                st.write(f"Error scraping {url}: {str(e)}")
                continue
        
        return articles
    
    def scrape_venture_beat_funding(self, num_articles: int = 5) -> List[Dict]:
        articles = []
        
        urls_to_try = [
            "https://venturebeat.com/category/deals/",
            "https://venturebeat.com/tag/funding/",
            "https://venturebeat.com/"
        ]
        
        for url in urls_to_try:
            try:
                st.write(f"Trying VentureBeat: {url}")
                
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                elements = (
                    soup.find_all('article', limit=num_articles * 2) or
                    soup.find_all('div', class_=re.compile(r'post.*'), limit=num_articles * 2) or
                    soup.find_all('h2', limit=num_articles * 2)
                )
                
                for element in elements:
                    if len(articles) >= num_articles:
                        break
                    
                    try:
                        title_elem = element.find(['h2', 'h3', 'h1'])
                        if not title_elem:
                            continue
                        
                        link_elem = title_elem.find('a') or element.find('a')
                        if not link_elem:
                            continue
                        
                        title = title_elem.get_text().strip()
                        link = link_elem.get('href', '')
                        
                        if link.startswith('/'):
                            link = urljoin(url, link)
                        
                        funding_keywords = ['funding', 'raises', 'investment', 'series', 'million', 'startup']
                        if any(keyword in title.lower() for keyword in funding_keywords):
                            excerpt_elem = element.find('p')
                            excerpt = excerpt_elem.get_text().strip()[:200] + "..." if excerpt_elem else ""
                            
                            articles.append({
                                'title': title,
                                'link': link,
                                'excerpt': excerpt,
                                'date': "",
                                'source': 'VentureBeat'
                            })
                            st.write(f"added VentureBeat: {title[:50]}...")
                    
                    except Exception as e:
                        continue
                
                if articles:
                    break
            
            except Exception as e:
                st.write(f"Error scraping VentureBeat {url}: {str(e)}")
                continue
        
        return articles
    
    def get_sample_funding_data(self) -> List[Dict]:
        sample_articles = [
            {
                'title': 'AI Startup Anthropic Raises $300M Series C for Constitutional AI Research',
                'link': 'https://example.com/anthropic-funding',
                'excerpt': 'Anthropic, the AI safety company, has raised $300 million in Series C funding to advance research in Constitutional AI and safety-focused language models...',
                'date': '2024-01-15',
                'source': 'Sample Data'
            },
            {
                'title': 'FinTech Startup Brex Secures $200M to Expand Corporate Credit Solutions',
                'link': 'https://example.com/brex-funding',
                'excerpt': 'Corporate credit card company Brex announced a $200 million funding round to expand its financial services platform for startups and enterprises...',
                'date': '2024-01-14',
                'source': 'Sample Data'
            },
            {
                'title': 'HealthTech Company Ro Raises $150M Series D for Telehealth Platform',
                'link': 'https://example.com/ro-funding',
                'excerpt': 'Digital health platform Ro has secured $150 million in Series D funding to expand its telehealth services and direct-to-consumer healthcare model...',
                'date': '2024-01-13',
                'source': 'Sample Data'
            },
            {
                'title': 'E-commerce Analytics Startup Triple Whale Gets $50M Series B',
                'link': 'https://example.com/triple-whale-funding',
                'excerpt': 'E-commerce analytics platform Triple Whale raised $50 million in Series B funding to help online retailers optimize their marketing and operations...',
                'date': '2024-01-12',
                'source': 'Sample Data'
            },
            {
                'title': 'Climate Tech Startup Watershed Raises $100M for Carbon Management',
                'link': 'https://example.com/watershed-funding',
                'excerpt': 'Carbon accounting platform Watershed secured $100 million to help enterprises measure and reduce their carbon footprint through advanced analytics...',
                'date': '2024-01-11',
                'source': 'Sample Data'
            }
        ]
        return sample_articles

class FundingAnalyzer:
    """AI agent for analyzing funding trends and extracting insights"""
    
    def __init__(self, llm):
        self.llm = llm
        self.prompt = PromptTemplate(
            input_variables=["funding_news"],
            template="""You are an expert startup and venture capital analyst. Analyze the following funding news articles and provide insights.

FUNDING NEWS ARTICLES:
{funding_news}

Please provide a comprehensive analysis including:

**1. TOP FUNDED SECTORS:**
- Which industries/sectors are getting the most funding
- Emerging trends in each sector

**2. FUNDING PATTERNS:**
- Common funding amounts and stages
- Geographic patterns
- Notable investors mentioned

**3. STARTUP TRENDS:**
- What types of startups are raising money
- Common business models
- Technology trends

**4. KEY INSIGHTS:**
- Market opportunities
- Investor preferences
- Risk factors to consider

**5. ACTIONABLE RECOMMENDATIONS:**
- Promising sectors for new startups
- Funding strategies
- Market gaps to explore

Format your response with clear headers and bullet points. Be specific and cite examples from the articles when possible."""
        )
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)
    
    def analyze(self, funding_news: str) -> str:
        return self.chain.run(funding_news=funding_news)

class IdeaGenerator:
    """AI agent for generating startup ideas based on funding trends"""
    
    def __init__(self, llm):
        self.llm = llm
        self.prompt = PromptTemplate(
            input_variables=["market_analysis", "focus_area", "additional_context"],
            template="""You are a creative startup idea generator and business strategist. Based on the market analysis and trends, generate innovative startup ideas.

MARKET ANALYSIS:
{market_analysis}

FOCUS AREA: {focus_area}

ADDITIONAL CONTEXT: {additional_context}

Generate 5-7 innovative startup ideas that could attract funding based on current trends. For each idea provide:

**IDEA NAME:** [Creative name]
**SECTOR:** [Industry/Category]
**PROBLEM:** [What problem it solves]
**SOLUTION:** [How it works]
**TARGET MARKET:** [Who would use it]
**BUSINESS MODEL:** [How it makes money]
**FUNDING POTENTIAL:** [Why investors would be interested]
**COMPETITIVE ADVANTAGE:** [What makes it unique]
**MVP SUGGESTION:** [How to start small]

**ADDITIONAL CONSIDERATIONS:**
- Focus on ideas that align with current funding trends
- Consider emerging technologies (AI, blockchain, IoT, etc.)
- Think about underserved markets
- Consider B2B vs B2C opportunities
- Factor in scalability and market size

Be creative but realistic. Provide ideas that could realistically be executed by a small team initially."""
        )
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)
    
    def generate(self, market_analysis: str, focus_area: str = "", additional_context: str = "") -> str:
        return self.chain.run(
            market_analysis=market_analysis,
            focus_area=focus_area,
            additional_context=additional_context
        )

class CompetitorAnalyzer:
    """AI agent for analyzing competitive landscape"""
    
    def __init__(self, llm):
        self.llm = llm
        self.prompt = PromptTemplate(
            input_variables=["startup_idea", "funding_data"],
            template="""You are a competitive intelligence analyst. Analyze the competitive landscape for a startup idea based on recent funding data.

STARTUP IDEA:
{startup_idea}

RECENT FUNDING DATA:
{funding_data}

Provide a competitive analysis including:

**1. DIRECT COMPETITORS:**
- Companies in the same space that recently raised funding
- Their funding amounts and stages
- Key differentiators

**2. INDIRECT COMPETITORS:**
- Adjacent companies that could pivot into this space
- Potential threats from big tech companies

**3. MARKET OPPORTUNITY:**
- Market size and growth potential
- Underserved segments
- Geographic opportunities

**4. COMPETITIVE POSITIONING:**
- How to differentiate from existing players
- Unique value propositions to consider
- Potential partnerships

**5. RISK ASSESSMENT:**
- Competition risks
- Market saturation concerns
- Barriers to entry

**6. STRATEGIC RECOMMENDATIONS:**
- Go-to-market strategy
- Timing considerations
- Funding strategy

Be specific and reference actual companies from the funding data when relevant."""
        )
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)
    
    def analyze(self, startup_idea: str, funding_data: str) -> str:
        return self.chain.run(startup_idea=startup_idea, funding_data=funding_data)

def format_articles_for_analysis(articles: List[Dict]) -> str:
    """Format scraped articles for AI analysis"""
    formatted_text = ""
    for i, article in enumerate(articles, 1):
        formatted_text += f"""
ARTICLE {i}:
Title: {article['title']}
Source: {article['source']}
Date: {article['date']}
Link: {article['link']}
Content: {article['excerpt']}

---
"""
    return formatted_text

def main():
    st.title("💡 Startup Idea Finder & Funding Tracker")
    st.markdown("### Discover trending startup ideas based on real funding data")
    
    debug_mode = st.sidebar.checkbox("🐛 Debug Mode", help="Show detailed scraping information")
    
    with st.sidebar:
        st.header("🔧 Configuration")
        
        model_options = [
            "llama3.2", "llama3.1", "llama3", "llama2",  
            "mistral", "phi3", "gemma2"
        ]
        
        selected_model = st.selectbox(
            "Select Ollama Model:",
            model_options,
            index=0
        )
        
        st.header("📊 Data Sources")
        
        use_sample_data = st.checkbox(
            "Use Sample Data (Skip Scraping)",
            value=False,
            help="Use predefined sample data instead of web scraping"
        )
        
        st.header("📊 Research Parameters")
        
        num_articles = st.slider(
            "Number of articles to analyze:",
            min_value=5,
            max_value=25,
            value=10,
            help="More articles = better analysis but slower processing"
        )
        
        focus_areas = [
            "All Sectors", "AI/Machine Learning", "Fintech", "Healthcare", 
            "E-commerce", "SaaS/B2B", "Consumer Apps", "Climate Tech",
            "EdTech", "PropTech", "Web3/Crypto", "Gaming", "IoT/Hardware"
        ]
        
        focus_area = st.selectbox(
            "Focus Area:",
            focus_areas,
            help="Focus analysis on specific sectors"
        )
        
        additional_context = st.text_area(
            "Additional Context:",
            placeholder="e.g., interested in B2B solutions, have technical background, targeting specific geographic markets...",
            height=100
        )
        
        st.markdown("---")
        st.info("""
        **Data Sources:**
        - TechCrunch Startups
        - VentureBeat Funding
        - Sample data (fallback)
        
        **Analysis includes:**
        - Funding trends
        - Sector analysis  
        - Startup ideas
        - Competitive landscape
        """)
    
    llm = get_llm(selected_model)
    if not llm:
        st.error("Failed to initialize language model. Please check Ollama setup.")
        st.stop()
    
    try:
        funding_analyzer = FundingAnalyzer(llm)
        idea_generator = IdeaGenerator(llm)
        competitor_analyzer = CompetitorAnalyzer(llm)
        scraper = WebScraper()
        st.success(f"✅ AI agents initialized with {selected_model}")
    except Exception as e:
        st.error(f"Error initializing agents: {str(e)}")
        st.stop()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("Generate Startup Ideas")
        
        if st.button("🔍 Research & Generate Ideas", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                all_articles = []
                
                if use_sample_data:
                    status_text.text("Using sample funding data...")
                    progress_bar.progress(30)
                    
                    all_articles = scraper.get_sample_funding_data()
                    st.success(f"Using {len(all_articles)} sample articles")
                    
                else:
                    status_text.text("Scraping funding news from various sources...")
                    progress_bar.progress(10)
                    
                    with st.spinner("Fetching latest funding news..."):
                        if debug_mode:
                            st.write("🔍 Starting TechCrunch scraping...")
                        
                        techcrunch_articles = scraper.scrape_techcrunch_funding(num_articles)
                        time.sleep(2)  
                        
                        if debug_mode:
                            st.write(f"TechCrunch results: {len(techcrunch_articles)} articles")
                            st.write("🔍 Starting VentureBeat scraping...")
                        
                        venturebeat_articles = scraper.scrape_venture_beat_funding(min(num_articles//2, 5))
                        
                        if debug_mode:
                            st.write(f"VentureBeat results: {len(venturebeat_articles)} articles")
                        
                        all_articles = techcrunch_articles + venturebeat_articles
                    
                    if not all_articles:
                        st.warning("Web scraping didn't find articles. Using sample data instead.")
                        all_articles = scraper.get_sample_funding_data()
                
                if not all_articles:
                    st.error("No funding articles found even with sample data.")
                    return
                
                st.success(f"Analyzing {len(all_articles)} funding articles")
                
                # Analyze funding trends
                status_text.text("Analyzing funding trends and patterns...")
                progress_bar.progress(40)
                
                formatted_articles = format_articles_for_analysis(all_articles)
                
                with st.spinner("Analyzing market trends..."):
                    market_analysis = funding_analyzer.analyze(formatted_articles)
                
                # Generate startup ideas
                status_text.text("Generating startup ideas...")
                progress_bar.progress(70)
                
                focus_context = f"Focus on {focus_area}" if focus_area != "All Sectors" else ""
                
                with st.spinner("Creating innovative startup ideas..."):
                    startup_ideas = idea_generator.generate(
                        market_analysis, focus_context, additional_context
                    )
                
                # Analyze idea's competition 
                status_text.text("Analyzing competitive landscape...")
                progress_bar.progress(90)
                
                with st.spinner("Analyzing competition..."):
                    first_idea = startup_ideas.split("**IDEA NAME:**")[1].split("**SECTOR:**")[0] if "**IDEA NAME:**" in startup_ideas else "AI-powered business solution"
                    competitive_analysis = competitor_analyzer.analyze(first_idea, formatted_articles)
                
                progress_bar.progress(100)
                status_text.text("Analysis complete!")
                
                st.session_state['last_analysis_data'] = {
                    'articles': all_articles,
                    'market_analysis': market_analysis,
                    'startup_ideas': startup_ideas,
                    'competitive_analysis': competitive_analysis
                }
                
                tab1, tab2, tab3, tab4 = st.tabs([
                    "Market Analysis", 
                    "Startup Ideas", 
                    "Competitive Analysis",
                    "Source Articles"
                ])
                
                with tab1:
                    st.markdown("### Market & Funding Analysis")
                    st.markdown(market_analysis)
                
                with tab2:
                    st.markdown("### Generated Startup Ideas")
                    st.markdown(startup_ideas)
                    
                    st.download_button(
                        "Download Ideas",
                        startup_ideas,
                        file_name=f"startup_ideas_{datetime.now().strftime('%Y%m%d')}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                
                with tab3:
                    st.markdown("### Competitive Landscape Analysis")
                    st.markdown(competitive_analysis)
                
                with tab4:
                    st.markdown("### Source Articles")
                    
                    for article in all_articles:
                        with st.expander(f"{article['title']} - {article['source']}"):
                            st.write(f"**Date:** {article['date']}")
                            if article['link'].startswith('http'):
                                st.write(f"**Link:** [View Article]({article['link']})")
                            else:
                                st.write(f"**Link:** {article['link']}")
                            st.write(f"**Excerpt:** {article['excerpt']}")
                
            except Exception as e:
                st.error(f"Error occurred: {str(e)}")
                st.error("Please try again or enable 'Use Sample Data' option.")
                if debug_mode:
                    st.exception(e)
    
    with col2:
        st.header("Quick Stats")
        
        if st.session_state.get('last_analysis_data'):
            data = st.session_state['last_analysis_data']
            
            st.metric("Articles Analyzed", len(data.get('articles', [])))
            st.metric("Ideas Generated", "5-7")
            st.metric("Sectors Covered", "Multiple")
            
            articles = data.get('articles', [])
            if articles:
                sources = {}
                for article in articles:
                    source = article['source']
                    sources[source] = sources.get(source, 0) + 1
                
                st.write("**Sources:**")
                for source, count in sources.items():
                    st.write(f"- {source}: {count} articles")
        else:
            st.info("Run analysis to see statistics")
        
        st.markdown("---")
        
        st.header("Custom Analysis")
        
        with st.expander("Analyze Specific Idea"):
            custom_idea = st.text_area(
                "Enter your startup idea:",
                placeholder="e.g., AI-powered personal finance app for Gen Z users",
                height=100
            )
            
            if st.button("Analyze This Idea") and custom_idea:
                if llm:
                    with st.spinner("Analyzing your idea..."):
                        if st.session_state.get('last_analysis_data'):
                            articles = st.session_state['last_analysis_data']['articles']
                        else:
                            articles = scraper.get_sample_funding_data()
                        
                        formatted_articles = format_articles_for_analysis(articles)
                        analysis = competitor_analyzer.analyze(custom_idea, formatted_articles)
                        
                        st.markdown("### Analysis Results")
                        st.markdown(analysis)
        
    

if __name__ == "__main__":
    main()
