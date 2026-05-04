from pydantic import BaseModel, UUID4
from typing import Optional
from enum import Enum
from datetime import datetime


class ReportReason(str, Enum):
    wrong_answer   = 'wrong_answer'
    wrong_question = 'wrong_question'
    ambiguous      = 'ambiguous'
    outdated       = 'outdated'
    other          = 'other'


class ReportStatus(str, Enum):
    pending         = 'pending'
    agent_reviewing = 'agent_reviewing'
    valid_replaced  = 'valid_replaced'
    valid_edited    = 'valid_edited'
    rejected        = 'rejected'
    human_override  = 'human_override'


# POST /quiz/report — student submits
class QuestionReportCreate(BaseModel):
    question_id:  UUID4
    session_id:   UUID4
    reason:       ReportReason
    student_note: Optional[str] = None


# Immediate response to student
class QuestionReportAck(BaseModel):
    report_id: UUID4
    status:    ReportStatus
    message:   str


# Full detail for reviewer dashboard
class QuestionReportOut(BaseModel):
    id:               UUID4
    question_id:      UUID4
    question_text:    Optional[str] = None
    session_id:       UUID4
    reported_by:      UUID4
    reason:           ReportReason
    student_note:     Optional[str]
    status:           ReportStatus
    agent_verdict:    Optional[str]
    agent_confidence: Optional[float]
    replacement_q_id: Optional[UUID4]
    reviewed_by:      Optional[UUID4]
    reviewer_note:    Optional[str]
    created_at:       Optional[str]
    resolved_at:      Optional[str]

    model_config = {'from_attributes': True}


# PATCH override — human reviewer
class ReviewerOverride(BaseModel):
    action:          str             # 'accept_replace' | 'accept_edit' | 'reject'
    reviewer_note:   Optional[str] = None
    edited_question: Optional[dict] = None  # used when action='accept_edit'


# Agent internal schema (not exposed to API)
class AgentDecision(BaseModel):
    is_valid:      bool
    confidence:    float
    verdict:       str
    action:        str             # 'replace' | 'edit' | 'reject'
    edited_fields: Optional[dict] = None   # new Q data if replace/edit


# Aggregate stats schema
class ReportStats(BaseModel):
    total:         int
    pending:       int
    agent_reviewing: int
    valid_replaced: int
    valid_edited:  int
    rejected:      int
    human_override: int
    by_reason:     dict
