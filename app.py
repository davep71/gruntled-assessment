import streamlit as st
import pandas as pd
from datetime import datetime
import streamlit.components.v1 as components
import json
import os
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF

# Add data persistence functions
def save_assessment_results(scores, timestamp):
    if not os.path.exists('data'):
        os.makedirs('data')
    
    results = {
        'scores': scores,
        'timestamp': timestamp.isoformat()
    }
    
    filename = f"assessment_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
    with open(f'data/{filename}', 'w') as f:
        json.dump(results, f)

def load_all_results():
    results = []
    if os.path.exists('data'):
        for filename in os.listdir('data'):
            if filename.endswith('.json'):
                with open(f'data/{filename}', 'r') as f:
                    results.append(json.load(f))
    return results

# Add coach authentication
def is_coach():
    return 'coach' in st.query_params and st.query_params['coach'] == 'gruntled_coach_access'

# Function to calculate dimension score and get analysis
def calculate_dimension_score(scores, dimension_key):
    if dimension_key not in scores:
        return 0
    return sum(scores[dimension_key].values())

def show_coach_summary():
    st.title("Coach View - Assessment Results")
    
    # Check if data directory exists
    if not os.path.exists('data'):
        st.warning("No assessments found.")
        return
    
    # Get all assessment files from the data directory
    assessments = []
    for filename in os.listdir('data'):
        if filename.endswith('.json'):
            with open(os.path.join('data', filename), 'r') as f:
                try:
                    assessment = json.load(f)
                    assessment['filename'] = filename  # Store filename for deletion
                    # Use a default date for sorting if assessment_start is missing
                    if 'assessment_start' not in assessment:
                        assessment['assessment_start'] = '1970-01-01T00:00:00'
                    assessments.append(assessment)
                except json.JSONDecodeError:
                    continue
    
    if not assessments:
        st.warning("No assessments found.")
        return
    
    # Sort assessments by date (most recent first)
    assessments.sort(key=lambda x: x.get('assessment_start', '1970-01-01T00:00:00'), reverse=True)
    
    # Create tabs for each assessment
    assessment_tabs = st.tabs([f"{assessment.get('coachee_name', 'Unknown')} - {datetime.fromisoformat(assessment['assessment_start']).strftime('%B %d, %Y')}" 
                             for assessment in assessments])
    
    # Show each assessment in its own tab
    for tab, assessment in zip(assessment_tabs, assessments):
        with tab:
            # Add delete button with confirmation
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button('Delete Assessment', key=f"delete_{assessment['filename']}"):
                    st.session_state[f"confirm_delete_{assessment['filename']}"] = True
                
            # Show confirmation message if delete was clicked
            if st.session_state.get(f"confirm_delete_{assessment['filename']}", False):
                st.warning("Are you sure you want to delete this assessment?")
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("Yes, Delete", key=f"confirm_yes_{assessment['filename']}"):
                        os.remove(os.path.join('data', assessment['filename']))
                        st.success("Assessment deleted successfully!")
                        st.rerun()
                with col2:
                    if st.button("No, Cancel", key=f"confirm_no_{assessment['filename']}"):
                        st.session_state[f"confirm_delete_{assessment['filename']}"] = False
                        st.rerun()
            
            # Format date for display
            assessment_date = datetime.fromisoformat(assessment['assessment_start']).strftime('%B %d, %Y at %I:%M %p')
            
            # Coachee Information
            st.markdown("""
                <div style='background-color: #F8F8F8; padding: 20px; border-radius: 10px; margin-bottom: 20px;'>
                    <h3>Coachee Information</h3>
                    <p><strong>Name:</strong> {name}</p>
                    <p><strong>Email:</strong> {email}</p>
                    <p><strong>Phone:</strong> {phone}</p>
                    <p><strong>Assessment Date:</strong> {date}</p>
                </div>
            """.format(
                name=assessment.get('coachee_name', 'Unknown'),
                email=assessment.get('coachee_email', 'Unknown'),
                phone=assessment.get('coachee_phone', 'Not provided'),
                date=assessment_date
            ), unsafe_allow_html=True)
            
            # Calculate dimension scores
            dimension_scores = {}
            for dimension_key, scores in assessment['scores'].items():
                dimension_scores[dimension_key] = sum(scores.values())
            
            # Create radar chart
            categories = [dimensions[key]['title'] for key in dimension_scores.keys()]
            values = list(dimension_scores.values())
            categories.append(categories[0])
            values.append(values[0])
            
            fig = go.Figure(data=go.Scatterpolar(
                r=values,
                theta=categories,
                fill='toself',
                fillcolor='rgba(228, 230, 163, 0.5)',
                line=dict(color='#F09C23')
            ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 60]
                    )
                ),
                showlegend=False,
                height=500
            )
            
            # Add unique key for each plotly chart
            chart_key = f"chart_{assessment.get('coachee_email', 'unknown')}_{assessment.get('assessment_start', 'unknown')}_{assessments.index(assessment)}"
            st.plotly_chart(fig, use_container_width=True, key=chart_key)
            
            # Add export to PDF button
            if st.button("Export to PDF", key=f"pdf_{assessment['filename']}"):
                pdf_content = generate_assessment_pdf(assessment, dimension_scores)
                st.download_button(
                    label="Download PDF Report",
                    data=pdf_content,
                    file_name=f"{assessment.get('coachee_name', 'Unknown')}_assessment.pdf",
                    mime="application/pdf",
                    key=f"download_{assessment['filename']}"
                )

            # Show dimension scores with interpretations and detailed breakdown
            st.markdown("### Leadership Dimensions Analysis")
            
            # Create tabs for each dimension
            dimension_tabs = st.tabs([f"{dimensions[key]['title']} - : {score}/60" 
                                    for key, score in dimension_scores.items()])
            
            for dim_tab, (dimension_key, score) in zip(dimension_tabs, dimension_scores.items()):
                with dim_tab:
                    # Show score bar
                    st.markdown(f"""
                        <div style='background-color: #F8F8F8; padding: 15px; border-radius: 10px; margin: 10px 0;'>
                            <div style='background-color: #E4E6A3; height: 20px; width: {(score/60)*100}%; border-radius: 5px;'></div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Get interpretation based on score
                    if score >= 51:
                        level = 'high'
                    elif score >= 41:
                        level = 'medium_high'
                    elif score >= 31:
                        level = 'medium'
                    elif score >= 21:
                        level = 'medium_low'
                    else:
                        level = 'low'
                    
                    # Show interpretation
                    interpretation = score_interpretations[dimension_key][level]
                    st.markdown("#### Analysis")
                    st.write(interpretation['interpretation'])
                    st.markdown("#### Development Focus")
                    st.write(interpretation['development'])
                    
                    # Show detailed breakdown of questions and scores
                    st.markdown("#### Detailed Responses")
                    for statement_key, statement in dimensions[dimension_key]['statements'].items():
                        score = assessment['scores'][dimension_key][statement_key]
                        st.markdown(f"- {statement}: **{score}/10**")

def generate_assessment_pdf(assessment, dimension_scores):
    pdf = FPDF()
    pdf.add_page()
    
    # Add title and logo
    pdf.image("assets/Horizontal.png", x=10, y=10, w=80)
    pdf.ln(30)
    
    # Add coachee information
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Leadership Assessment Report", ln=True)
    pdf.ln(5)
    
    # Coachee details
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Coachee Information", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Name: {assessment.get('coachee_name', 'Unknown')}", ln=True)
    pdf.cell(0, 10, f"Email: {assessment.get('coachee_email', 'Unknown')}", ln=True)
    pdf.cell(0, 10, f"Phone: {assessment.get('coachee_phone', 'Not provided')}", ln=True)
    assessment_date = datetime.fromisoformat(assessment['assessment_start']).strftime('%B %d, %Y at %I:%M %p')
    pdf.cell(0, 10, f"Assessment Date: {assessment_date}", ln=True)
    pdf.ln(10)
    
    # Dimension scores
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Leadership Dimensions Analysis", ln=True)
    pdf.ln(5)
    
    for dimension_key, score in dimension_scores.items():
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, f"{dimensions[dimension_key]['title']}: {score}/60", ln=True)
        
        # Get interpretation
        if score >= 51:
            level = 'high'
        elif score >= 41:
            level = 'medium_high'
        elif score >= 31:
            level = 'medium'
        elif score >= 21:
            level = 'medium_low'
        else:
            level = 'low'
            
        interpretation = score_interpretations[dimension_key][level]
        
        # Add interpretation
        pdf.set_font("Arial", "", 10)
        pdf.multi_cell(0, 10, f"Analysis: {interpretation['interpretation']}")
        pdf.multi_cell(0, 10, f"Development Focus: {interpretation['development']}")
        pdf.ln(5)
    
    return pdf.output(dest='S').encode('latin-1')
# Configure the page
st.set_page_config(
    page_title="Gruntled Leadership Assessment",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Brand colors
colors = {
    'night': '#101010',
    'davys_gray': '#4C4D4F',
    'non_photo_blue': '#9CD4E0',
    'vanilla': '#E4E6A3',
    'gamboge': '#F09C23'
}
# Custom CSS with wizard styling
st.markdown("""
    <style>
    .main {
        background-color: #FFFFFF;
    }
    .stTitle {
        color: #101010;
        font-size: 28px;
        font-weight: bold;
        margin-bottom: 30px;
    }
    .stButton>button {
        background-color: #F09C23;
        color: #101010;
        font-weight: bold;
        padding: 10px 25px;
        border-radius: 5px;
        border: none;
        transition: background-color 0.3s;
    }
    .stButton>button:hover {
        background-color: #E4E6A3;
    }
    /* Content container */
    .content-container {
        display: flex;
        gap: 30px;
        margin-top: 20px;
    }
    /* Assessment container */
    .assessment-container {
        flex: 7;
        padding: 20px;
        background-color: #FFFFFF;
        border-radius: 10px;
    }
    /* Rating scale container */
    .rating-box {
        flex: 3;
        background-color: #F8F8F8;
        padding: 25px;
        border-radius: 10px;
        border-left: 4px solid #F09C23;
        position: sticky;
        top: 20px;
        height: fit-content;
    }
    .rating-title {
        color: #101010;
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 20px;
    }
    .rating-item {
        margin: 12px 0;
        font-size: 16px;
        line-height: 1.4;
    }
    /* Statement styling */
    .statement-text {
        font-size: 20px;
        color: #101010;
        margin: 20px 0;
        line-height: 1.4;
    }
    /* Navigation buttons */
    .nav-buttons {
        display: flex;
        justify-content: space-between;
        margin-top: 30px;
        padding-top: 20px;
        border-top: 1px solid #F8F8F8;
    }
    /* Slider styling */
    .stSlider > div > div > div {
        background-color: #9CD4E0;
    }
    .stSlider > div > div > div > div {
        background-color: #F09C23;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = 'welcome'
if 'scores' not in st.session_state:
    st.session_state.scores = {}
if 'start_time' not in st.session_state:
    st.session_state.start_time = datetime.now()
if 'coachee_name' not in st.session_state:
    st.session_state.coachee_name = None
if 'coachee_email' not in st.session_state:
    st.session_state.coachee_email = None
if 'coachee_phone' not in st.session_state:
    st.session_state.coachee_phone = None
if 'assessment_start' not in st.session_state:
    st.session_state.assessment_start = None
if 'current_question' not in st.session_state:
    st.session_state.current_question = 0

    def is_coach():
        return st.query_params.get('coach', '') == 'gruntled_coach_access'

def save_assessment_data():
    """Save assessment data to a JSON file"""
    if not os.path.exists('data'):
        os.makedirs('data')
    
    # Calculate dimension scores
    dimension_scores = {}
    for dimension_key, scores in st.session_state.scores.items():
        dimension_scores[dimension_key] = sum(scores.values())
    
    assessment_data = {
        'coachee_name': st.session_state.coachee_name,
        'coachee_email': st.session_state.coachee_email,
        'coachee_phone': st.session_state.coachee_phone,
        'assessment_start': st.session_state.assessment_start,
        'completion_time': datetime.now().isoformat(),
        'scores': st.session_state.scores,
        'dimension_scores': dimension_scores
    }
    
    # Create filename using coachee email and timestamp
    filename = f"assessment_{st.session_state.coachee_email}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # Save to file
    with open(os.path.join('data', filename), 'w') as f:
        json.dump(assessment_data, f)
# Header
st.image("assets/Horizontal.png", width=300)

# Dictionary of all dimensions and their statements
dimensions = {
    'purpose_vision': {
        'title': 'Purpose & Vision',
        'statements': {
            'vision': "Creates and effectively communicates a compelling vision for the future",
            'values': "Clearly defines and consistently reinforces organizational values through actions",
            'strategic': "Considers long-term implications and broader context in decision making",
            'meaningful': "Helps others understand how their work contributes to larger organizational goals",
            'legacy': "Takes actions today that will have positive long-term impact on the organization",
            'why': "Clearly communicates the 'why' behind decisions and direction"
        }
    },
    'execution_impact': {
        'title': 'Execution & Impact',
        'statements': {
            'prioritize': "Effectively prioritizes tasks and initiatives based on strategic importance",
            'resources': "Allocates and manages resources efficiently to achieve desired outcomes",
            'quality': "Consistently delivers high-quality results that meet or exceed expectations",
            'expectations': "Establishes and maintains clear performance expectations and accountability",
            'goals': "Sets specific, measurable, achievable, relevant, and time-bound goals",
            'recognition': "Recognizes and appreciates others' contributions and achievements"
        }
    },
    'trust_authenticity': {
        'title': 'Trust & Authenticity',
        'statements': {
            'listening': "Practices active listening and demonstrates clear understanding of others' perspectives",
            'sharing': "Shares information clearly and openly with others",
            'conversations': "Engages in difficult conversations with candor and respect",
            'safety': "Creates an environment where team members feel safe to speak up and take risks",
            'followthrough': "Does what they say they will do by following through on commitments",
            'attention': "Gives full, undivided attention during interactions with others"
        }
    },
    'emotional_intelligence': {
        'title': 'Emotional Intelligence',
        'statements': {
            'awareness': "Demonstrates awareness of own emotions and their impact on others",
            'composure': "Maintains composure and effectiveness under pressure",
            'recognition': "Recognizes and appropriately responds to others' emotions and needs",
            'respect': "Consistently treats all people with dignity and respect",
            'conflict': "Addresses and resolves conflicts constructively and professionally",
            'feedback': "Seeks and acts on feedback about own performance"
        }
    },
    'people_development': {
        'title': 'People Development',
        'statements': {
            'learning': "Actively supports and encourages continuous learning and development",
            'coaching': "Provides effective coaching and mentoring to develop others' capabilities",
            'strengths': "Identifies and leverages individual and team member strengths",
            'growth': "Helps team members identify and pursue career growth opportunities",
            'boundaries': "Supports healthy work-life boundaries and personal well-being",
            'motivation': "Understands and responds to what motivates different team members"
        }
    },
    'team_leadership': {
        'title': 'Team Leadership',
        'statements': {
            'collaboration': "Promotes effective collaboration and teamwork across the group",
            'decisions': "Involves team members appropriately in decisions that affect their work",
            'viewpoints': "Actively seeks and incorporates different viewpoints and ideas",
            'environment': "Creates a positive team environment where people enjoy their work",
            'unity': "Actively breaks down silos and promotes organizational unity",
            'recognition': "Recognizes team and individual contributions meaningfully"
        }
    },
    'change_management': {
    'title': 'Change Management',
    'statements': {
        'strategy': "Develops clear change implementation strategies",
        'pace': "Effectively manages the pace and sequence of change",
        'resistance': "Identifies and constructively addresses resistance to change",
        'execution': "Develops and executes well-structured plans for implementing change",
        'sustainability': "Ensures changes are successfully embedded and sustained over time",
        'assumptions': "Challenges personal assumptions and biases during change"
        }
    },
    'strategic_influence': {
        'title': 'Strategic Influence',
        'statements': {
            'boundaries': "Effectively influences decisions and actions across organizational boundaries",
            'stakeholders': "Builds and maintains productive relationships with key stakeholders",
            'community': "Actively engages in and promotes community service and social responsibility",
            'innovation': "Promotes and supports innovative thinking and creative solutions",
            'trends': "Anticipates future trends and positions the organization for success",
            'networks': "Builds strong networks across the organization and community"
        }
    }
}
# Function to generate randomized questions
def generate_randomized_questions():
    if 'randomized_questions' not in st.session_state:
        all_questions = []
        for dimension_key, dimension in dimensions.items():
            for statement_key, statement in dimension['statements'].items():
                all_questions.append({
                    'dimension_key': dimension_key,
                    'statement_key': statement_key,
                    'statement': statement,
                    'question_number': len(all_questions) + 1
                })
        
        # Randomize the questions
        import random
        random.shuffle(all_questions)
        
        # Store in session state
        st.session_state.randomized_questions = all_questions
        
    return st.session_state.randomized_questions

# Function to get current question
def get_current_question():
    questions = generate_randomized_questions()
    if st.session_state.current_question < len(questions):
        return questions[st.session_state.current_question]
    return None

# Score interpretations dictionary
score_interpretations = {
    'purpose_vision': {
        'high': {
            'range': (51, 60),
            'interpretation': "Demonstrates exceptional strategic leadership with clear vision articulation and execution. Consistently connects organizational purpose to daily operations while helping others see their role in the bigger picture. Shows sophisticated understanding of how values drive behavior and decisions.",
            'development': "Lead enterprise-wide strategic initiatives. Mentor other leaders in vision development and strategic communication. Create frameworks for vision deployment across multiple organizational levels."
        },
        'medium_high': {
            'range': (41, 50),
            'interpretation': "Shows strong capability in strategic thinking and vision communication. Successfully translates organizational goals into actionable plans. Effectively reinforces values through consistent behavior.",
            'development': "Practice articulating more complex strategic concepts. Develop systematic approaches to connecting daily work to organizational purpose. Seek opportunities to influence strategic direction beyond immediate area."
        },
        'medium': {
            'range': (31, 40),
            'interpretation': "Demonstrates growing strategic capability but may struggle with consistent implementation. Shows basic understanding of vision importance and values alignment. Sometimes connects daily work to larger purpose but could be more proactive.",
            'development': "Build strategic thinking skills through structured exercises and mentoring. Practice translating organizational vision into team-specific goals. Work with mentor on developing more sophisticated approaches."
        },
        'medium_low': {
            'range': (21, 30),
            'interpretation': "Shows basic understanding of vision's importance but struggles with practical application. May focus primarily on tactical execution with limited strategic perspective. Inconsistent in connecting work to larger organizational purpose.",
            'development': "Start with fundamental strategic thinking concepts. Learn basic vision communication techniques. Practice connecting daily decisions to organizational values."
        },
        'low': {
            'range': (0, 20),
            'interpretation': "Primarily focused on immediate tasks with limited strategic awareness. May struggle to see beyond day-to-day operations. Needs significant development in strategic thinking and vision communication.",
            'development': "Begin with basic concepts of organizational purpose and values. Learn fundamental strategic thinking tools. Practice articulating simple strategic goals."
        }
    } ,
          'execution_impact': {
        'high': {
            'range': (51, 60),
            'interpretation': "Demonstrates exceptional ability to deliver results while maintaining highest quality standards. Expertly balances multiple priorities and resources to achieve optimal outcomes. Shows sophisticated understanding of goal-setting and accountability processes.",
            'development': "Lead organizational effectiveness initiatives. Mentor others in project and resource management. Create frameworks for goal-setting and accountability."
        },
        'medium_high': {
            'range': (41, 50),
            'interpretation': "Shows strong capability in delivering results and managing resources. Successfully balances multiple priorities most of the time. Demonstrates good understanding of goal-setting and accountability.",
            'development': "Enhance project management skills through advanced training. Build expertise in resource optimization. Develop more sophisticated approaches to performance management."
        },
        'medium': {
            'range': (31, 40),
            'interpretation': "Demonstrates growing ability in execution but may lack consistency. Shows basic understanding of resource management and goal-setting. Sometimes struggles with balancing priorities.",
            'development': "Build structured approach to project management. Practice resource allocation techniques. Work on developing more effective goal-setting systems."
        },
        'medium_low': {
            'range': (21, 30),
            'interpretation': "Shows basic understanding of execution principles but struggles with implementation. May focus more on activity than results. Inconsistent in resource management or quality standards.",
            'development': "Learn fundamental project management principles. Practice basic priority-setting techniques. Develop simple but effective accountability systems."
        },
        'low': {
            'range': (0, 20),
            'interpretation': "Limited understanding of execution principles and practices. May struggle with basic resource management or quality standards. Needs significant growth in fundamental management skills.",
            'development': "Start with basic concepts of project management. Learn fundamental resource allocation principles. Practice simple goal-setting techniques."
        }
    },
        'trust_authenticity': {
        'high': {
            'range': (51, 60),
            'interpretation': "Demonstrates exceptional ability to build and maintain trust through consistent authentic behavior. Creates strong psychological safety where team members freely share ideas and take risks. Shows sophisticated understanding of active listening and follow-through.",
            'development': "Lead organizational trust-building initiatives. Mentor others in creating psychological safety. Create frameworks for authentic leadership development."
        },
        'medium_high': {
            'range': (41, 50),
            'interpretation': "Shows strong capability in building trust and maintaining authenticity. Successfully creates safe environments for open dialogue. Demonstrates good understanding of active listening and follow-through.",
            'development': "Enhance trust-building skills through advanced training. Build expertise in creating psychological safety. Develop more sophisticated approaches to difficult conversations."
        },
        'medium': {
            'range': (31, 40),
            'interpretation': "Demonstrates growing ability in trust-building but may lack consistency. Shows basic understanding of psychological safety and authentic behavior. Sometimes struggles with active listening or follow-through.",
            'development': "Build structured approach to trust-building. Practice active listening techniques. Work on developing more effective communication strategies."
        },
        'medium_low': {
            'range': (21, 30),
            'interpretation': "Shows basic understanding of trust principles but struggles with implementation. May create unintended barriers to psychological safety. Inconsistent in listening or follow-through.",
            'development': "Learn fundamental trust-building principles. Practice basic listening techniques. Develop simple but effective communication strategies."
        },
        'low': {
            'range': (0, 20),
            'interpretation': "Limited understanding of trust-building principles and practices. May inadvertently undermine psychological safety. Needs significant growth in basic communication skills.",
            'development': "Start with basic concepts of trust-building. Learn fundamental listening principles. Practice simple communication techniques."
        }
    },
         'emotional_intelligence': {
        'high': {
            'range': (51, 60),
            'interpretation': "Demonstrates exceptional self-awareness and emotional regulation. Expertly reads and responds to others' emotional needs. Shows sophisticated understanding of conflict resolution and relationship management. Particularly skilled at maintaining composure under pressure.",
            'development': "Lead organizational EQ development initiatives. Mentor others in emotional intelligence growth. Create frameworks for conflict resolution. Share best practices in building emotionally intelligent cultures."
        },
        'medium_high': {
            'range': (41, 50),
            'interpretation': "Shows strong capability in emotional awareness and regulation. Successfully reads and responds to others' emotions. Demonstrates good understanding of conflict resolution. Generally effective at maintaining composure under pressure.",
            'development': "Enhance emotional intelligence through advanced training. Build expertise in conflict resolution. Develop more sophisticated approaches to relationship management."
        },
        'medium': {
            'range': (31, 40),
            'interpretation': "Demonstrates growing emotional awareness but may lack consistency. Shows basic understanding of others' emotions and conflict resolution. Sometimes struggles with composure under pressure.",
            'development': "Build structured approach to emotional awareness. Practice emotion regulation techniques. Work on developing more effective conflict resolution strategies."
        },
        'medium_low': {
            'range': (21, 30),
            'interpretation': "Shows basic understanding of emotional intelligence but struggles with implementation. May miss emotional cues or react inappropriately. Inconsistent in conflict resolution or composure.",
            'development': "Learn fundamental emotional intelligence principles. Practice basic emotion regulation techniques. Develop simple but effective conflict resolution approaches."
        },
        'low': {
            'range': (0, 20),
            'interpretation': "Limited understanding of emotional intelligence principles and practices. May struggle with basic emotional awareness or regulation. Needs significant growth in fundamental relationship skills.",
            'development': "Start with basic concepts of emotional intelligence. Learn fundamental emotion regulation principles. Practice simple conflict resolution techniques."
        }
    },
           'people_development': {
        'high': {
            'range': (51, 60),
            'interpretation': "Demonstrates exceptional ability to develop others through structured and informal approaches. Shows sophisticated understanding of individual learning styles and motivation. Creates robust development plans that align personal growth with organizational needs.",
            'development': "Lead organizational development initiatives. Create mentoring programs and frameworks. Share best practices in talent development. Consider speaking or writing about development approaches."
        },
        'medium_high': {
            'range': (41, 50),
            'interpretation': "Shows strong capability in developing others and understanding motivation. Successfully creates and implements development plans. Demonstrates good ability to identify and leverage strengths. Generally effective at maintaining appropriate boundaries.",
            'development': "Enhance coaching skills through advanced training. Build expertise in talent assessment. Develop more sophisticated approaches to motivation and engagement."
        },
        'medium': {
            'range': (31, 40),
            'interpretation': "Demonstrates growing ability in development but may lack consistency. Shows basic understanding of motivation and strength identification. Sometimes struggles with creating effective development plans.",
            'development': "Build structured approach to development conversations. Practice strength identification techniques. Work on creating more effective development plans."
        },
        'medium_low': {
            'range': (21, 30),
            'interpretation': "Shows basic understanding of development principles but struggles with implementation. May focus more on weaknesses than strengths. Inconsistent in motivation or boundary-setting.",
            'development': "Learn fundamental coaching principles. Practice basic motivation assessment. Develop simple but effective development planning skills."
        },
        'low': {
            'range': (0, 20),
            'interpretation': "Limited understanding of development principles and practices. May struggle with basic coaching or motivation. Needs significant growth in fundamental development skills.",
            'development': "Start with basic concepts of adult learning and development. Learn fundamental coaching principles. Practice simple strength identification techniques."
        }
    },
        'team_leadership': {
        'high': {
            'range': (51, 60),
            'interpretation': "Demonstrates exceptional ability to build and lead high-performing teams. Creates strong collaborative environments where diverse perspectives thrive. Shows sophisticated understanding of team dynamics and motivation. Particularly skilled at breaking down silos and fostering cross-functional cooperation.",
            'development': "Lead organizational team effectiveness initiatives. Mentor other leaders in team development. Create frameworks for cross-functional collaboration. Share best practices in building collaborative cultures."
        },
        'medium_high': {
            'range': (41, 50),
            'interpretation': "Shows strong capability in team leadership and collaboration. Successfully creates positive team environments. Demonstrates good understanding of team dynamics. Generally effective at managing diverse perspectives and breaking down silos.",
            'development': "Enhance team development skills through advanced training. Build expertise in managing complex team dynamics. Develop more sophisticated approaches to cross-functional collaboration."
        },
        'medium': {
            'range': (31, 40),
            'interpretation': "Demonstrates growing ability in team leadership but may lack consistency. Shows basic understanding of team dynamics and collaboration. Sometimes struggles with managing diverse perspectives or breaking down silos.",
            'development': "Build structured approach to team development. Practice inclusive decision-making techniques. Work on developing more effective collaboration strategies."
        },
        'medium_low': {
            'range': (21, 30),
            'interpretation': "Shows basic understanding of team leadership but struggles with implementation. May focus more on individual than team performance. Inconsistent in creating collaborative environments.",
            'development': "Learn fundamental team development principles. Practice basic collaboration techniques. Develop simple but effective team-building approaches."
        },
        'low': {
            'range': (0, 20),
            'interpretation': "Limited understanding of team leadership principles and practices. May struggle with basic team dynamics or collaboration. Needs significant growth in fundamental team leadership skills.",
            'development': "Start with basic concepts of team dynamics. Learn fundamental collaboration principles. Practice simple team-building techniques."
        }
    },
        'change_management': {
        'high': {
            'range': (51, 60),
            'interpretation': "Demonstrates exceptional ability to lead and implement complex change initiatives. Shows sophisticated understanding of change dynamics and resistance patterns. Particularly skilled at pacing and sequencing change while maintaining stakeholder engagement.",
            'development': "Lead enterprise-wide transformation initiatives. Mentor others in change management. Create frameworks for sustainable change implementation. Share best practices in change leadership."
        },
        'medium_high': {
            'range': (41, 50),
            'interpretation': "Shows strong capability in managing change processes. Successfully implements most change initiatives. Demonstrates good understanding of resistance patterns. Generally effective at maintaining stakeholder engagement and ensuring sustainability.",
            'development': "Enhance change management skills through advanced training. Build expertise in stakeholder engagement. Develop more sophisticated approaches to resistance management."
        },
        'medium': {
            'range': (31, 40),
            'interpretation': "Demonstrates growing ability in change management but may lack consistency. Shows basic understanding of change principles and resistance. Sometimes struggles with pacing or sustainability.",
            'development': "Build structured approach to change implementation. Practice resistance management techniques. Work on developing more effective stakeholder engagement strategies."
        },
        'medium_low': {
            'range': (21, 30),
            'interpretation': "Shows basic understanding of change management but struggles with implementation. May rush implementation or miss key stakeholder concerns. Inconsistent in addressing resistance or ensuring sustainability.",
            'development': "Learn fundamental change management principles. Practice basic stakeholder engagement techniques. Develop simple but effective change implementation approaches."
        },
        'low': {
            'range': (0, 20),
            'interpretation': "Limited understanding of change management principles and practices. May struggle with basic change implementation or stakeholder engagement. Needs significant growth in fundamental change management skills.",
            'development': "Start with basic concepts of change management. Learn fundamental stakeholder engagement principles. Practice simple change implementation techniques."
        }
    },
        'strategic_influence': {
        'high': {
            'range': (51, 60),
            'interpretation': "Demonstrates exceptional ability to influence across organizational boundaries. Shows sophisticated understanding of stakeholder management and relationship building. Particularly skilled at creating and leveraging networks while maintaining strong community connections.",
            'development': "Lead strategic partnership initiatives. Mentor others in stakeholder management. Create frameworks for innovation and future positioning. Share best practices in building influential networks."
        },
        'medium_high': {
            'range': (41, 50),
            'interpretation': "Shows strong capability in strategic influence and stakeholder management. Successfully builds and maintains key relationships. Demonstrates good understanding of innovation and future trends. Generally effective at building networks and community connections.",
            'development': "Enhance stakeholder management skills through advanced training. Build expertise in innovation leadership. Develop more sophisticated approaches to network building."
        },
        'medium': {
            'range': (31, 40),
            'interpretation': "Demonstrates growing ability in strategic influence but may lack consistency. Shows basic understanding of stakeholder management and networking. Sometimes struggles with innovation or future positioning.",
            'development': "Build structured approach to stakeholder management. Practice innovation techniques. Work on developing more effective networking strategies."
        },
        'medium_low': {
            'range': (21, 30),
            'interpretation': "Shows basic understanding of strategic influence but struggles with implementation. May focus more on immediate relationships than strategic ones. Inconsistent in stakeholder management or innovation support.",
            'development': "Learn fundamental stakeholder management principles. Practice basic networking techniques. Develop simple but effective innovation approaches."
        },
        'low': {
            'range': (0, 20),
            'interpretation': "Limited understanding of strategic influence principles and practices. May struggle with basic relationship building or stakeholder management. Needs significant growth in fundamental influence skills.",
            'development': "Start with basic concepts of stakeholder management. Learn fundamental networking principles. Practice simple innovation techniques."
        }
    }
}

# Function to show wizard page

def show_wizard_page():
    st.title("Leadership Assessment")
    
    # Get all questions and randomize if not already done
    if 'randomized_questions' not in st.session_state:
        questions = []
        for dimension_key, dimension in dimensions.items():
            for statement_key, statement in dimension['statements'].items():
                questions.append({
                    'dimension_key': dimension_key,
                    'statement_key': statement_key,
                    'statement': statement,
                    'question_number': len(questions) + 1
                })
        
        # Randomize the questions
        import random
        random.shuffle(questions)
        st.session_state.randomized_questions = questions
    
    questions = st.session_state.randomized_questions

    # Show questions
    for index, q in enumerate(questions, 1):  # enumerate starting from 1
        st.markdown(f"""
            <div style='background-color: #F8F8F8; padding: 20px; border-radius: 10px; margin: 10px 0;'>
                <div class='statement-text'>*{index}. {q['statement']}</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Create dropdown with descriptions
        options = {
            1: "Does not yet demonstrate this behavior",
            2: "Very rarely demonstrates this behavior",
            3: "Rarely demonstrates this behavior",
            4: "Occasionally demonstrates this behavior",
            5: "Inconsistently demonstrates this behavior",
            6: "Sometimes demonstrates this behavior",
            7: "Often demonstrates this behavior",
            8: "Frequently demonstrates this behavior",
            9: "Consistently exemplifies this behavior",
            10: "Consistently exemplifies this behavior and teaches others"
        }
        
        selected = st.selectbox(
            "",
            sorted(options.keys()),
            format_func=lambda x: f"{x} - {options[x]}",
            key=f"q_{q['question_number']}",
            label_visibility="collapsed"
        )
        
        # Store the response
        if selected:
            if q['dimension_key'] not in st.session_state.scores:
                st.session_state.scores[q['dimension_key']] = {}
            st.session_state.scores[q['dimension_key']][q['statement_key']] = selected
    
    # Complete button
    st.markdown("<div style='text-align: center; margin-top: 30px;'>", unsafe_allow_html=True)
    if st.button("Complete Assessment", use_container_width=True):
        save_assessment_data()  # Add this line
        st.session_state.page = 'thank_you'
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
# Main routing
if is_coach():
    show_coach_summary()
elif st.session_state.page == 'welcome':
    st.title("Leadership Assessment")
    st.markdown("""
        <div style='background-color: #F8F8F8; padding: 25px; border-radius: 10px; border-left: 4px solid #F09C23;'>
            <h3 style='color: #101010;'>Welcome to the Gruntled Leadership Assessment</h3>
            <p style='font-size: 18px;'>This assessment consists of 48 questions and will take approximately 12-16 minutes to complete.</p>
            <p style='font-size: 18px;'>Your honest responses will help identify areas of strength and opportunities for growth.</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Add form for coachee information
    with st.form(key="coachee_info_form"):
        st.write("### Please provide your information")
        name = st.text_input("Full Name*")
        email = st.text_input("Email Address*")
        phone = st.text_input("Phone Number")
        
        submitted = st.form_submit_button("Begin Assessment")
        
        if submitted:
            if name and email:  # Basic validation
                # Store coachee info in session state
                st.session_state['coachee_name'] = name
                st.session_state['coachee_email'] = email
                st.session_state['coachee_phone'] = phone
                st.session_state['assessment_start'] = datetime.now().isoformat()
                st.session_state.page = 'assessment'
                st.rerun()
            else:
                st.error("Please fill in all required fields marked with *")

elif st.session_state.page == 'assessment':
    show_wizard_page()

elif st.session_state.page == 'thank_you':
    # Add anchor for top of page
    st.markdown("<div id='top'></div>", unsafe_allow_html=True)
    
    # Calculate dimension scores
    dimension_scores = {}
    for dimension_key, scores in st.session_state.scores.items():
        dimension_scores[dimension_key] = sum(scores.values())
    
    st.title("Assessment Complete")
    
    # Show overall summary
    st.markdown("""
        <div style='background-color: #F8F8F8; padding: 25px; border-radius: 10px; border-left: 4px solid #F09C23;'>
            <h3 style='color: #101010;'>Thank you for completing the assessment</h3>
            <p style='font-size: 18px;'>Your responses have been recorded and a detailed report will be reviewed during your upcoming discovery call.</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Rest of your thank you page code...
    
    # Create radar chart (adjust scale to match 0-60)
    categories = [dimensions[key]['title'] for key in dimension_scores.keys()]
    values = list(dimension_scores.values())
    
    # Add the first value again to close the polygon
    categories.append(categories[0])
    values.append(values[0])
    
    fig = go.Figure(data=go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        fillcolor='rgba(228, 230, 163, 0.5)',
        line=dict(color='#F09C23')
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 60]  # Update range to 0-60
            )
        ),
        showlegend=False,
        height=500
    )
    
    # Display the radar chart
    st.plotly_chart(fig, use_container_width=True)
    
    # Show dimension scores
    st.markdown("### Your Leadership Dimensions")
    
    for dimension_key, score in dimension_scores.items():
        col1, col2 = st.columns([7, 3])
        with col1:
            st.markdown(f"""
                <div style='background-color: #F8F8F8; padding: 15px; border-radius: 10px; margin: 10px 0;'>
                    <h4>{dimensions[dimension_key]['title']}</h4>
                    <div style='background-color: #E4E6A3; height: 20px; width: {(score/60)*100}%; border-radius: 5px;'></div>
                </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div style='padding: 15px; font-size: 24px; text-align: center;'>{score}/60</div>", unsafe_allow_html=True)

    # Show detailed breakdown
    with st.expander("View Detailed Breakdown"):
        for dimension_key in dimensions:
            st.markdown(f"### {dimensions[dimension_key]['title']}")
            for statement_key, statement in dimensions[dimension_key]['statements'].items():
                score = st.session_state.scores[dimension_key][statement_key]
                st.markdown(f"- {statement}: **{score}/10**")
            st.markdown("---")
    
    # Next steps
    st.markdown("""
        <div style='background-color: #F8F8F8; padding: 25px; border-radius: 10px; margin-top: 30px;'>
            <h3 style='color: #101010;'>Next Steps</h3>
            <p style='font-size: 18px;'>A Gruntled Leadership coach will contact you at {st.session_state.coachee_email} to schedule your discovery call 
            to discuss your results and potential growth opportunities.</p>
        </div>
    """, unsafe_allow_html=True)


elif st.session_state.page in dimensions:
    show_wizard_page(st.session_state.page)