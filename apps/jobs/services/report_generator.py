import json
import openai
from django.conf import settings
from apps.jobs.models import Application, AIAnswer, CandidateReport
import logging
from apps.jobs.models import AuditLog

openai.api_key = settings.OPENAI_API_KEY
logger = logging.getLogger('zecpath.ai')
error_logger = logging.getLogger('django')


class CandidateReportService:
    @staticmethod
    def generate_report(application_id, requested_by_user):
        logger.info(f"Initiating AI report generation for Application ID: {application_id}")
        application = Application.objects.get(id=application_id)
        
        # 1. Return existing report if already generated (saves API costs)
        if hasattr(application, 'report'):
            return application.report
            
        # 2. Gather Data (Handling missing fields gracefully)
        # Assuming you have an 'ats_score' on your Application model. Default to 0 if not.
        ats_score = getattr(application, 'ats_score', 0) or 0 
        
        if not hasattr(application, 'interview_session'):
            raise ValueError("Cannot generate report: No interview session found.")
            
        answers = AIAnswer.objects.filter(question__session=application.interview_session)
        if not answers.exists():
            raise ValueError("Cannot generate report: Interview transcript is empty.")
            
        try:
            # Calculate Average Interview Score
            interview_score = sum(ans.final_score for ans in answers if ans.final_score) / answers.count()
            
            # Combine transcript for context
            transcript_text = "\n".join([f"Q: {a.question.question_text}\nA: {a.answer_text}" for a in answers])

            # 3. Calculate Overall Algorithm Score (30% Resume ATS, 70% Live AI Interview)
            overall_score = (float(ats_score) * 0.3) + (float(interview_score) * 0.7)

            # 4. Generate Insights using OpenAI Structured JSON
            prompt = f"""
            You are an expert Technical Recruiter evaluating a candidate for the {application.job.title} role.
            Resume ATS Score: {ats_score}/100
            AI Interview Score: {interview_score}/100
            
            Interview Transcript:
            {transcript_text}
            
            Based on this data, generate a JSON report with strictly these keys:
            - "summary": A 3-sentence executive summary of the candidate's fit for the role.
            - "strengths": An array of 3 specific technical or soft-skill strengths (strings).
            - "risks": An array of 1-2 potential risks, weaknesses, or areas for concern (strings).
            """
            
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            insights = json.loads(response.choices[0].message.content)

            # Mock data
            # insights = {
            #     "summary": "[MOCK DATA] The candidate demonstrated excellent knowledge of backend systems but hit an OpenAI billing limit during the interview.",
            #     "strengths": ["Resilience in debugging", "Strong Django architecture skills", "API Integration"],
            #     "risks": ["Needs to top up OpenAI API credits"]
            # }
            
            # 5. Save and Return the Report
            report = CandidateReport.objects.create(
                application=application,
                overall_score=round(overall_score, 2),
                summary=insights.get('summary', 'No summary generated.'),
                strengths=insights.get('strengths', []),
                risks=insights.get('risks', [])
            )
            AuditLog.objects.create(
                user=requested_by_user,
                action='GENERATED_AI_REPORT',
                target_object_id=str(application_id),
                details={"overall_score": overall_score}
            )
            logger.info(f"Successfully generated AI report for Application {application_id}")
            return report
        except openai.RateLimitError as e:
            # 3. Failure Tracking: AI specific issues
            error_logger.error(f"OpenAI Rate Limit Exceeded for Application {application_id}. Retry required.")
            raise ValueError("AI Service is temporarily unavailable due to rate limits.")

        except Exception as e:
            # 4. Global Exception Alert
            error_logger.exception(f"Critical failure generating report for Application {application_id}: {str(e)}")
            raise ValueError("An unexpected error occurred during AI evaluation.")
        
        