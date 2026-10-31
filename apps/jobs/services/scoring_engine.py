import json
import openai
from django.conf import settings
from apps.jobs.models import AIAnswer

openai.api_key = settings.OPENAI_API_KEY

class AnswerScoringEngine:
    @classmethod
    def evaluate_and_score(cls, answer_instance):
        """Evaluates the answer and updates the AIAnswer instance in the DB."""
        question_text = answer_instance.question.question_text
        candidate_text = answer_instance.answer_text

        prompt = f"""
        You are a strict technical evaluator. 
        Question: "{question_text}"
        Candidate's Answer: "{candidate_text}"
        
        Evaluate the answer and return a JSON object with strictly these keys:
        - "relevance": integer 0-100 (Does the answer directly address the question?)
        - "completeness": integer 0-100 (Did they provide sufficient detail/keywords?)
        - "feedback": string (One concise sentence of constructive feedback)
        """

        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=150,
                temperature=0.3 # Low temperature for consistent scoring
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Save the annotations
            answer_instance.relevance_score = result.get('relevance', 0)
            answer_instance.completeness_score = result.get('completeness', 0)
            answer_instance.feedback = result.get('feedback', 'No feedback provided.')
            
            # Run normalization logic
            answer_instance.calculate_normalized_score()
            answer_instance.save()
            
            return answer_instance
            
        except Exception as e:
            # Fallback for API failure
            answer_instance.feedback = "Error evaluating answer."
            answer_instance.save()
            return None