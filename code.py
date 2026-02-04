import streamlit as st
import threading
import time
import json
import requests
import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ================== CONFIG ==================
load_dotenv()
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

engine = create_engine("sqlite:///jobs.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ================== DATABASE MODEL ==================
class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    taskName = Column(String, nullable=False)
    payload = Column(JSON)
    priority = Column(String)
    status = Column(String, default="pending")
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow)
    completedAt = Column(DateTime, nullable=True)

Base.metadata.create_all(bind=engine)

# ================== WEBHOOK FUNCTION ==================
def trigger_webhook(job):
    try:
        data = {
            "jobId": job.id,
            "taskName": job.taskName,
            "priority": job.priority,
            "payload": job.payload,
            "completedAt": str(job.completedAt),
        }
        response = requests.post(WEBHOOK_URL, json=data)
        print("Webhook sent:", response.status_code)
    except Exception as e:
        print("Webhook error:", e)

# ================== JOB RUNNER ==================
def run_job_background(job_id):
    db = SessionLocal()
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return

    job.status = "running"
    job.updatedAt = datetime.utcnow()
    db.commit()

    time.sleep(3)  # simulate processing

    job.status = "completed"
    job.completedAt = datetime.utcnow()
    job.updatedAt = datetime.utcnow()
    db.commit()

    trigger_webhook(job)
    db.close()

# ================== STREAMLIT UI ==================
st.set_page_config(page_title="Dotix Job Scheduler", layout="wide")
st.title("⚙️ Job Scheduler & Automation System")

menu = st.sidebar.radio("Navigation", ["Create Job", "Dashboard"])

# ================== CREATE JOB ==================
if menu == "Create Job":
    st.subheader("➕ Create New Job")

    task_name = st.text_input("Task Name")
    priority = st.selectbox("Priority", ["Low", "Medium", "High"])
    payload_text = st.text_area("Payload (JSON)", '{"example":"data"}')

    if st.button("Create Job"):
        try:
            payload = json.loads(payload_text)
            db = SessionLocal()
            new_job = Job(
                taskName=task_name,
                payload=payload,
                priority=priority,
                status="pending",
            )
            db.add(new_job)
            db.commit()
            db.close()
            st.success("Job created successfully!")
        except Exception as e:
            st.error(f"Invalid JSON: {e}")

# ================== DASHBOARD ==================
elif menu == "Dashboard":
    st.subheader("📋 Job Dashboard")

    status_filter = st.selectbox("Filter by Status", ["All", "pending", "running", "completed"])
    priority_filter = st.selectbox("Filter by Priority", ["All", "Low", "Medium", "High"])

    db = SessionLocal()
    jobs = db.query(Job).all()
    db.close()

    # Apply filters
    if status_filter != "All":
        jobs = [j for j in jobs if j.status == status_filter]
    if priority_filter != "All":
        jobs = [j for j in jobs if j.priority == priority_filter]

    for job in jobs:
        with st.expander(f"Job #{job.id} — {job.taskName} ({job.status.upper()})"):
            st.write("**Priority:**", job.priority)
            st.write("**Created At:**", job.createdAt)
            st.write("**Updated At:**", job.updatedAt)
            st.write("**Completed At:**", job.completedAt)
            st.json(job.payload)

            if job.status == "pending":
                if st.button(f"Run Job {job.id}"):
                    threading.Thread(target=run_job_background, args=(job.id,)).start()
                    st.warning("Job started... Refresh to see updates.")

    st.info("Refresh page to see live job status updates.")
