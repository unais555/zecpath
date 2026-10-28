import openai
from django.conf import settings
from apps.jobs.models import AIInterviewSession, JobScreeningTemplate, AIQuestion

openai.api_key = settings.OPENAI_API_KEY

class AIFlowManager: 
    def __init__(self, session_id):
        self.session = AIInterviewSession.objects.get(id=session_id)
        self.job = self.session.application.job
        self.templates = list(self.job.screening_templates.all().order_by('order'))

    def process_candidate_answer(self, candidate_text):
        """Processes the STT input and determines the next state."""
        if self.session.is_completed:
            return "Interview is already complete."

        current_template = self.templates[self.session.current_question_index]

        # 1. Evaluate Response using LLM
        evaluation = self._evaluate_completeness(current_template.base_question, candidate_text)

        # 2. Branching Logic
        if evaluation['is_complete'] or not current_template.requires_follow_up:
            # Move to next question
            self.session.current_question_index += 1
            self.session.awaiting_follow_up = False
            
            if self.session.current_question_index >= len(self.templates):
                self.session.is_completed = True
                self.session.save()
                return "Thank you so much for your time. We have all the information we need, and our team will get back to you shortly."
            
            self.session.save()
            return self._generate_next_question()
        else:
            # 3. Dynamic Follow-up Triggered
            self.session.awaiting_follow_up = True
            self.session.save()
            return evaluation['follow_up_question']

    def _generate_next_question(self):
        """Fetches the next template and makes it conversational."""
        current_template = self.templates[self.session.current_question_index]
        
        # Log the question in the database (from Day 34)
        AIQuestion.objects.create(
            session=self.session,
            question_text=current_template.base_question,
            order=self.session.current_question_index
        )
        
        return current_template.base_question

    def _evaluate_completeness(self, original_question, candidate_answer):
        """Uses OpenAI to determine if the candidate actually answered the question, or if a follow-up is needed."""
        prompt = f"""
        You are an expert technical recruiter. 
        Original Question: "{original_question}"
        Candidate Answer: "{candidate_answer}"
        
        Did the candidate answer the question satisfactorily? 
        If yes, reply strictly with: COMPLETE
        If no, reply with a short, conversational follow-up question asking for the missing details.
        """
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": prompt}],
                max_tokens=50,
                temperature=0.7
            )
            ai_reply = response.choices[0].message.content.strip()
            
            if ai_reply == "COMPLETE":
                return {"is_complete": True, "follow_up_question": None}
            else:
                return {"is_complete": False, "follow_up_question": ai_reply}
                
        except Exception as e:
            # Fallback logic: if OpenAI fails, just assume complete to keep the call moving
            return {"is_complete": True, "follow_up_question": None}