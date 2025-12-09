from db import db_get, db_all


def calculate_matching_percentage(candidate_id, job_id):
    """
    Calculate matching percentage between candidate profile and job requirements.
    Returns a percentage (0-100) based on:
    - Role match (from experiences)
    - Experience level match
    - Location preference
    - Education relevance
    """
    try:
        # Get candidate profile
        profile = db_get('SELECT * FROM candidate_profiles WHERE candidate_id = ?', (candidate_id,))
        if not profile:
            return 0
        
        # Get job details
        job = db_get('SELECT * FROM jobs WHERE jdid = ?', (job_id,))
        if not job:
            return 0
        
        score = 0
        max_score = 0
        
        # 1. Role/Experience Match (40 points max)
        max_score += 40
        job_title = (job.get('title') or '').lower()
        job_description = (job.get('description') or '').lower()
        
        # Get candidate experiences
        experiences = db_all(
            'SELECT role, company FROM candidate_experiences WHERE candidate_id = ?',
            (candidate_id,)
        )
        
        role_match = False
        for exp in experiences:
            role = (exp.get('role') or '').lower()
            if role and (role in job_title or any(word in job_description for word in role.split())):
                role_match = True
                break
        
        if role_match:
            score += 40
        elif experiences:
            # Partial match if candidate has any experience
            score += 20
        
        # 2. Experience Level Match (20 points max)
        max_score += 20
        job_experience = job.get('experience') or ''
        candidate_experience_level = profile.get('experience_level') or ''
        
        if job_experience and candidate_experience_level:
            job_exp_lower = job_experience.lower()
            cand_exp_lower = candidate_experience_level.lower()
            
            # Check for matches
            if 'senior' in job_exp_lower and 'senior' in cand_exp_lower:
                score += 20
            elif 'junior' in job_exp_lower and 'junior' in cand_exp_lower:
                score += 20
            elif 'mid' in job_exp_lower and ('mid' in cand_exp_lower or 'intermediate' in cand_exp_lower):
                score += 20
            elif 'fresher' in job_exp_lower and ('fresher' in cand_exp_lower or 'entry' in cand_exp_lower):
                score += 20
            elif candidate_experience_level:
                # Generic experience level exists
                score += 10
        
        # 3. Location Match (20 points max)
        max_score += 20
        job_location = (job.get('location') or '').lower()
        preferred_location = (profile.get('preferred_location') or '').lower()
        current_location = (profile.get('current_location') or '').lower()
        
        if job_location:
            if preferred_location and (job_location in preferred_location or preferred_location in job_location):
                score += 20
            elif current_location and (job_location in current_location or current_location in job_location):
                score += 15
            elif preferred_location or current_location:
                score += 5
        
        # 4. Education Relevance (10 points max)
        max_score += 10
        education = db_all(
            'SELECT degree FROM candidate_education WHERE candidate_id = ?',
            (candidate_id,)
        )
        if education and len(education) > 0:
            score += 10
        
        # 5. Profile Completeness (10 points max)
        max_score += 10
        if profile.get('completed'):
            score += 10
        
        # Calculate percentage
        if max_score == 0:
            return 0
        
        percentage = min(100, int((score / max_score) * 100))
        return percentage
        
    except Exception as e:
        print(f"Error calculating matching percentage: {e}")
        return 0

