# -*- coding: utf-8 -*-
"""
AI Support Copilot — FastAPI Backend
=====================================
Build Beyond Limits Hackathon | Powered by Valkey

Implements (from HACKATHON.md):
  Challenge 4  — Trending Incidents (Sorted Sets)
  Challenge 8  — Analytics + Prometheus /metrics
  Challenge 12 — Rate Limiting (Sliding Window)
  Challenge 13 — Recommendations (co-purchase pattern)
  Challenge 14 — Agentic Search (Conversation Memory)

Prerequisites:
  docker pull valkey/valkey-bundle:9-alpine
  docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9-alpine

Connection:
  VALKEY_URL=redis://localhost:6379
"""
import os
import time
import hashlib
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from copilot.id_utils import create_id
from copilot.trending_detector import TrendingDetector
from copilot.conversation_memory import ConversationMemory
from copilot.analytics import AnalyticsEngine
from copilot.escalation import EscalationManager
from copilot.rate_limiter import RateLimiter

# ── App ──────────────────────────────────────────────────────

app = FastAPI(
    title="AI Support Copilot",
    description=(
        "Valkey-powered intelligent support platform. "
        "Build Beyond Limits Hackathon — React Hyderabad."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singletons ───────────────────────────────────────────────

trending    = TrendingDetector()
memory      = ConversationMemory()
analytics   = AnalyticsEngine()
escalation  = EscalationManager()
rate_limiter = RateLimiter()

# ── ML resources (lazy) ──────────────────────────────────────

_ml = None

def _load_ml():
    global _ml
    if _ml is not None:
        return _ml
    try:
        import pickle, faiss
        import pandas as pd
        from sentence_transformers import SentenceTransformer
        with open("models/embed_model.pkl", "rb") as f:
            info = pickle.load(f)
        model    = SentenceTransformer(info["model_name"])
        articles = pd.read_pickle("models/articles_meta.pkl")
        index    = faiss.read_index("models/article_index.faiss")
        _ml = (model, articles, index)
        print("[ML] Loaded FAISS + SentenceTransformer")
    except Exception as e:
        print(f"[ML] Unavailable ({e}) — using mock KB articles")
        _ml = (None, None, None)
    return _ml

# ── Resolution engine (lazy) ─────────────────────────────────

_engine = None

def _get_engine():
    global _engine
    if _engine is None:
        try:
            from copilot.resolution_engine import ResolutionEngine
            _engine = ResolutionEngine()
        except Exception:
            _engine = None
    return _engine

# ── Helpers ──────────────────────────────────────────────────

MOCK_KB = [
    "Payment Troubleshooting Guide",
    "Account Recovery Steps",
    "Refund Policy & Process",
    "Login Issues Resolution",
    "API Error Codes Reference",
    "Delivery Tracking Help",
    "Billing Dispute Resolution",
    "Service Status Page Guide",
    "Password Reset Instructions",
    "Order Cancellation Policy",
]

def _get_recommendations(text: str, top_k: int = 3) -> list:
    """Semantic KB search via FAISS, or mock data."""
    model, articles, index = _load_ml()
    if model is None:
        import random, hashlib
        seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % 10000
        random.seed(seed)
        selected = random.sample(MOCK_KB, min(top_k, len(MOCK_KB)))
        scores   = sorted([random.uniform(0.45, 0.95) for _ in selected], reverse=True)
        return [
            {"rank": i+1, "article_title": t, "score": round(s, 3)}
            for i, (t, s) in enumerate(zip(selected, scores))
        ]
    import faiss as _faiss
    emb = model.encode([text], convert_to_numpy=True)
    _faiss.normalize_L2(emb)
    D, I = index.search(emb, top_k)
    return [
        {"rank": i+1, "article_title": articles.iloc[idx]["title"], "score": float(D[0][i])}
        for i, idx in enumerate(I[0])
    ]

def _resolve(confidence: float, text: str, recs: list) -> dict:
    """Run resolution engine or fallback."""
    engine = _get_engine()
    if engine:
        res = engine.determine_action(confidence, text, recs)
    else:
        if confidence >= 0.85:
            res = {
                "action": "auto_resolved", "confidence_tier": "high",
                "resolution": f"Resolved via: {recs[0]['article_title'] if recs else 'N/A'}",
                "source_article": recs[0]["article_title"] if recs else "N/A",
                "timestamp": datetime.utcnow().isoformat(),
            }
        elif confidence >= 0.50:
            res = {
                "action": "draft_response", "confidence_tier": "medium",
                "draft": "Suggested: " + ", ".join(r["article_title"] for r in recs[:2]) + ". [VERIFY]",
                "recommendations": recs[:3],
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            res = {
                "action": "escalated", "confidence_tier": "low",
                "summary": {
                    "issue_summary": text[:120],
                    "attempted_fixes": "KB semantic search — low confidence",
                    "probable_root_cause": "Requires human investigation",
                    "priority": "high",
                },
                "recommendations": recs[:3],
                "timestamp": datetime.utcnow().isoformat(),
            }
    res["confidence_score"] = confidence
    return res

def _rate_limit_headers(result: dict) -> dict:
    return {
        "X-RateLimit-Limit":     str(result["limit"]),
        "X-RateLimit-Remaining": str(result["remaining"]),
        "X-RateLimit-Reset":     str(result["reset"]),
    }

# ── Pydantic models ──────────────────────────────────────────

class TicketInput(BaseModel):
    ticket_id:   Optional[str]   = None
    ticket_text: str
    category:    Optional[str]   = None
    confidence:  Optional[float] = None

class AgentMessage(BaseModel):
    session_id:  Optional[str] = None
    message:     str
    user_id:     Optional[str] = None

class EscalationClaim(BaseModel):
    agent_name: str

class EscalationResolve(BaseModel):
    ticket_id:       str
    resolution_note: str

class DemoTicketBatch(BaseModel):
    tickets: list[dict]

# ════════════════════════════════════════════════════════════
# ROUTES
# ════════════════════════════════════════════════════════════

@app.get("/", tags=["Health"])
def root():
    return {
        "service":     "AI Support Copilot",
        "version":     "2.0.0",
        "status":      "running",
        "powered_by":  "valkey/valkey-bundle:9-alpine",
        "hackathon":   "Build Beyond Limits — React Hyderabad",
        "challenges":  ["4-Trending", "8-Analytics", "12-RateLimit",
                        "13-Recommendations", "14-AgenticSearch"],
        "docs":        "/docs",
        "metrics":     "/metrics",
    }

# ── Challenge 8: Prometheus metrics ─────────────────────────

@app.get("/metrics", response_class=PlainTextResponse, tags=["Analytics"])
def prometheus_metrics():
    """Prometheus exposition format — Challenge 8."""
    return analytics.prometheus_metrics()

# ── Core: Process ticket ─────────────────────────────────────

@app.post("/copilot/process", tags=["Copilot"])
def process_ticket(ticket: TicketInput, request: Request):
    """
    Full AI Copilot pipeline:
      1. Assign UUIDv7 ticket ID
      2. Detect category
      3. Semantic KB recommendations
      4. Confidence-based resolution (auto / draft / escalate)
      5. Record trending (Challenge 4)
      6. Store conversation memory (Challenge 14)
      7. Update analytics (Challenge 8)
      8. Rate limit check (Challenge 12)
    """
    t0 = time.time()

    # Rate limiting (Challenge 12)
    user_id = ticket.ticket_id or request.client.host or "anonymous"
    rl = rate_limiter.check(user_id, "/copilot/process", authenticated=bool(ticket.ticket_id))
    if not rl["allowed"]:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit_exceeded",
                    "message": f"Too many requests. Retry in {rl['retry_after']}s.",
                    "retry_after": rl["retry_after"]},
            headers=_rate_limit_headers(rl),
        )

    # Assign ID (UUIDv7 with domain prefix — hackathon spec)
    ticket_id = ticket.ticket_id or create_id("ticket")
    category  = ticket.category or trending.detect_category(ticket.ticket_text)

    # KB recommendations
    recs = _get_recommendations(ticket.ticket_text)
    confidence = ticket.confidence if ticket.confidence is not None else (
        recs[0]["score"] if recs else 0.5
    )

    # Resolution
    resolution = _resolve(confidence, ticket.ticket_text, recs)

    # Challenge 4: Trending
    trending.record_incident(category, ticket_id, action=resolution["action"])

    # Challenge 14: Conversation memory (JSON.SET)
    memory.create_conversation(ticket_id, ticket.ticket_text, category)
    memory.store_recommendations(ticket_id, recs)
    memory.store_resolution(ticket_id, resolution)
    memory.add_agent_turn(
        ticket_id,
        content=resolution.get("resolution") or resolution.get("draft") or "Escalated",
        action=resolution["action"],
    )

    # Challenge 8: Analytics
    latency_ms = (time.time() - t0) * 1000
    analytics.record_ticket(ticket_id, category, resolution["action"],
                            confidence, latency_ms)
    for rec in recs:
        analytics.record_kb_hit(rec["article_title"], rec["score"])

    # Escalation queue
    if resolution["action"] == "escalated":
        escalation.escalate_ticket(
            ticket_id=ticket_id,
            ticket_text=ticket.ticket_text,
            category=category,
            recommendations=recs,
            escalation_summary=resolution.get("summary", {}),
            confidence=confidence,
        )

    return Response(
        content=__import__("json").dumps({
            "ticket_id":       ticket_id,
            "category":        category,
            "confidence":      confidence,
            "action":          resolution["action"],
            "resolution":      resolution,
            "recommendations": recs,
            "timestamp":       datetime.utcnow().isoformat(),
            "latency_ms":      round(latency_ms, 2),
        }),
        media_type="application/json",
        headers=_rate_limit_headers(rl),
    )

# ── Challenge 14: Agentic Search ─────────────────────────────

@app.post("/agent/search", tags=["Agentic Search"])
def agent_search(msg: AgentMessage):
    """
    Natural language ticket search with conversation memory.
    Maintains context across turns (Challenge 14).
    """
    session_id = msg.session_id or create_id("session")

    # Check agent cache (avoid re-running expensive searches)
    from valkey_config import get_client, K
    cache_key = K.agent_cache(
        hashlib.md5(msg.message.encode()).hexdigest()
    )
    vk = get_client()
    cached = vk.get(cache_key)
    if cached:
        import json
        result = json.loads(cached)
        result["session_id"] = session_id
        result["cached"] = True
        return result

    # Get or create conversation
    conv = memory.get_conversation(session_id)
    if not conv:
        conv = memory.create_conversation(session_id, msg.message)

    # Detect category and get recommendations
    category = trending.detect_category(msg.message)
    recs     = _get_recommendations(msg.message, top_k=5)
    confidence = recs[0]["score"] if recs else 0.5

    # Build agent response
    resolution = _resolve(confidence, msg.message, recs)
    follow_up  = _build_follow_up(category, confidence)

    result = {
        "session_id":  session_id,
        "response":    resolution.get("resolution") or resolution.get("draft") or
                       "I've escalated this to a human agent with full context.",
        "action":      resolution["action"],
        "confidence":  confidence,
        "results":     [
            {
                "article_title": r["article_title"],
                "score":         r["score"],
                "reason":        f"Matched with {r['score']*100:.0f}% confidence",
            }
            for r in recs[:3]
        ],
        "follow_up":   follow_up,
        "context": {
            "intent":    "support_request",
            "category":  category,
            "turns":     len(conv.get("turns", [])) + 1,
        },
        "cached": False,
    }

    # Store agent turn in conversation memory
    memory.add_agent_turn(session_id, result["response"],
                          action=resolution["action"],
                          search_params={"category": category, "confidence": confidence})

    # Cache result for 5 minutes
    import json
    vk.set(cache_key, json.dumps(result), ex=300)

    # Record analytics
    analytics.record_ticket(session_id, category, resolution["action"], confidence)
    trending.record_incident(category, session_id, action=resolution["action"])

    return result

@app.get("/agent/conversation/{session_id}", tags=["Agentic Search"])
def get_conversation(session_id: str):
    """Get full conversation history for a session (Challenge 14)."""
    conv = memory.get_conversation(session_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv

# ── Challenge 4: Trending ────────────────────────────────────

@app.get("/trending", tags=["Trending"])
def get_trending(window: str = "1h"):
    """
    Trending incident categories.
    ZREVRANGE trending:global:{window} 0 9 WITHSCORES
    """
    return {
        "trending":     trending.get_trending(window=window),
        "all_scores":   trending.get_all_scores(),
        "spike_alerts": trending.get_spike_alerts(),
        "window":       window,
    }

@app.post("/events/view", tags=["Trending"])
def record_view(ticket: TicketInput):
    """Record a ticket view event (Challenge 4)."""
    cat = ticket.category or trending.detect_category(ticket.ticket_text)
    trending.record_incident(cat, ticket.ticket_id or "anon", action="view")
    return {"status": "recorded", "category": cat}

# ── Challenge 8: Analytics ───────────────────────────────────

@app.get("/analytics/live", tags=["Analytics"])
def live_analytics():
    """Real-time dashboard metrics."""
    return analytics.get_live_metrics()

@app.get("/analytics/trend", tags=["Analytics"])
def hourly_trend(hours: int = 12):
    """Hourly ticket volume (last N hours)."""
    return analytics.get_hourly_trend(hours=hours)

@app.get("/analytics/kb-performance", tags=["Analytics"])
def kb_performance():
    """KB article impression and score metrics."""
    return analytics.get_kb_performance(top_n=10)

@app.get("/analytics/activity-feed", tags=["Analytics"])
def activity_feed(count: int = 20):
    """Live activity stream from Valkey Streams."""
    return analytics.get_activity_feed(count=count)

@app.get("/analytics/dashboard", tags=["Analytics"])
def analytics_dashboard():
    """Combined dashboard data endpoint."""
    return {
        "live":          analytics.get_live_metrics(),
        "hourly_trend":  analytics.get_hourly_trend(hours=12),
        "kb_top10":      analytics.get_kb_performance(top_n=10),
        "trending":      trending.get_trending(),
        "spike_alerts":  trending.get_spike_alerts(),
        "escalation_queue_length": escalation.get_queue_length(),
    }

# ── Escalation queue ─────────────────────────────────────────

@app.get("/escalation/queue", tags=["Escalation"])
def get_escalation_queue():
    return {
        "queue": escalation.get_queue(),
        "stats": escalation.get_escalation_stats(),
    }

@app.post("/escalation/claim", tags=["Escalation"])
def claim_escalation(claim: EscalationClaim):
    result = escalation.claim_escalation(claim.agent_name)
    if not result:
        raise HTTPException(404, "No pending escalations")
    return result

@app.post("/escalation/resolve", tags=["Escalation"])
def resolve_escalation(body: EscalationResolve):
    result = escalation.resolve_escalation(body.ticket_id, body.resolution_note)
    if not result:
        raise HTTPException(404, "Escalation not found")
    return result

# ── Conversations ────────────────────────────────────────────

@app.get("/conversations/recent", tags=["Conversations"])
def recent_conversations():
    return memory.get_recent_conversations(limit=20)

@app.get("/conversation/{ticket_id}", tags=["Conversations"])
def get_ticket_conversation(ticket_id: str):
    conv = memory.get_conversation(ticket_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv

# ── Backward-compatible recommend endpoint ───────────────────

@app.post("/recommend", tags=["Recommendations"])
def recommend(ticket: TicketInput):
    """Backward-compatible endpoint from original project."""
    recs = _get_recommendations(ticket.ticket_text)
    return {
        "ticket_id":       ticket.ticket_id,
        "ticket_text":     ticket.ticket_text,
        "recommendations": recs,
    }

# ── Demo utilities ───────────────────────────────────────────

@app.get("/demo/sample-tickets", tags=["Demo"])
def sample_tickets():
    return [
        {"ticket_id": create_id("ticket"), "ticket_text": "I was charged twice for my subscription payment",    "category": "billing_dispute"},
        {"ticket_id": create_id("ticket"), "ticket_text": "Cannot login to my account, password reset not working", "category": "login_issue"},
        {"ticket_id": create_id("ticket"), "ticket_text": "API returning 500 errors on all endpoints since morning", "category": "api_error"},
        {"ticket_id": create_id("ticket"), "ticket_text": "My package shows delivered but I never received it",  "category": "delivery_complaint"},
        {"ticket_id": create_id("ticket"), "ticket_text": "Payment declined even though my card has sufficient balance", "category": "payment_failure"},
        {"ticket_id": create_id("ticket"), "ticket_text": "App crashes every time I try to open settings",       "category": "api_error"},
        {"ticket_id": create_id("ticket"), "ticket_text": "Need refund for order cancelled 3 days ago",          "category": "refund_request"},
        {"ticket_id": create_id("ticket"), "ticket_text": "Account locked after too many login attempts",        "category": "account_locked"},
        {"ticket_id": create_id("ticket"), "ticket_text": "Delivery delayed by 2 weeks, no tracking update",    "category": "delivery_complaint"},
        {"ticket_id": create_id("ticket"), "ticket_text": "Service completely down, cannot access any features", "category": "service_outage"},
        {"ticket_id": create_id("ticket"), "ticket_text": "Payment gateway timeout during checkout",             "category": "payment_failure"},
        {"ticket_id": create_id("ticket"), "ticket_text": "Wrong item delivered, need exchange",                 "category": "delivery_complaint"},
    ]

@app.post("/demo/batch", tags=["Demo"])
def demo_batch(batch: DemoTicketBatch, request: Request):
    """Batch process tickets for demo population."""
    results = []
    for t in batch.tickets:
        ticket = TicketInput(
            ticket_id=t.get("ticket_id"),
            ticket_text=t.get("ticket_text", ""),
            category=t.get("category"),
            confidence=t.get("confidence"),
        )
        result = process_ticket(ticket, request)
        import json
        results.append(json.loads(result.body))
    return {"processed": len(results), "results": results}

@app.post("/demo/reset", tags=["Demo"])
def demo_reset():
    """Reset all Valkey data for a fresh demo."""
    trending.reset_scores()
    analytics.reset_analytics()
    escalation.clear_queue()
    return {"status": "reset", "message": "All Valkey data cleared"}

# ── Helpers ──────────────────────────────────────────────────

def _build_follow_up(category: str, confidence: float) -> str:
    if confidence >= 0.85:
        return "Is there anything else I can help you with?"
    if category == "payment_failure":
        return "Would you like me to check your recent transactions or connect you with billing?"
    if category == "login_issue":
        return "Should I guide you through account recovery or escalate to the security team?"
    if category == "delivery_complaint":
        return "Would you like real-time tracking information or to file a missing item report?"
    return "Would you like me to refine the search or escalate to a human agent?"

import hashlib
