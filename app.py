import streamlit as st
from agents.data_ingestion_agent import DataIngestionAgent
from agents.feature_extraction_agent import FeatureExtractionAgent
from agents.priority_calculation_agent import PriorityCalculationAgent
from agents.priority_queue_management_agent import PriorityQueueManagementAgent
from agents.real_time_monitoring_agent import RealTimeMonitoringAgent
from utils.database import Appointment, Session
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import os
import json

load_dotenv()

def main():
    st.title("Physician Chamber Appointment System")

    # Initialize agents
    ingestion_agent = DataIngestionAgent()
    feature_agent = FeatureExtractionAgent()
    priority_calc_agent = PriorityCalculationAgent()
    queue_agent = PriorityQueueManagementAgent()
    monitoring_agent = RealTimeMonitoringAgent()

    # Initialize Session state for queue
    if "queue" not in st.session_state:
        st.session_state.queue = []

    def clear_database():
        """Clears all data from the database."""
        session = Session()
        try:
            session.query(Appointment).delete()
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Error clearing database: {e}")
        finally:
            session.close()

    # Function to load data from PDF
    def load_appointments():
        uploaded_file = st.file_uploader("Upload your PDF here", type=["pdf"])
        if uploaded_file is not None:
            try:
                with open("temp.pdf", "wb") as f:
                   f.write(uploaded_file.read())
                clear_database()
                ingestion_agent.ingest_data('temp.pdf')
                st.success("Appointments loaded successfully!")
                st.session_state.queue = queue_agent.get_prioritized_queue()
                st.rerun()
            except Exception as e:
                 st.error(f"Error loading appointments: {e}")


    # load appointments from pdf if the queue is empty.
    if not st.session_state.queue:
        load_appointments()

    # Load the queue from database if it exists in session state.
    if st.session_state.queue:
        # Load the queue from database.
          queue = queue_agent.get_prioritized_queue()

          # Convert queue to dataframe
          df = pd.DataFrame([{"id": appt.id,
                             "patient_name": appt.patient_name,
                             "type": appt.type,
                             "check_in_time": appt.check_in_time,
                             "priority_score": appt.priority_score,
                             "sl": appt.sl,
                             "is_checked_in": appt.is_checked_in
                            } for appt in queue])

          # Check in functionality
          def check_in_patient(patient_id):
               monitoring_agent.check_in(patient_id)
               priority_calc_agent.update_priority_in_db(patient_id)
               st.session_state.queue = queue_agent.get_prioritized_queue()
               st.rerun()


          def mark_appointment_done(patient_id):
                session = Session()
                try:
                    appointment = session.query(Appointment).filter(Appointment.id == patient_id).first()
                    if appointment:
                        appointment.is_completed = True
                        session.commit()
                        st.session_state.queue = queue_agent.get_prioritized_queue()
                        st.rerun()
                except Exception as e:
                    session.rollback()
                    print(f"Error marking the appointment complete {e}")
                finally:
                    session.close()



          # Define the check in and done button click
          def handle_button_click(patient_id, button_type):
             if button_type == "check_in":
                  check_in_patient(patient_id)
             elif button_type == "done":
                  mark_appointment_done(patient_id)

          # Create the HTML table
          html_table = f"""
             <table style='width: 100%; border-collapse: collapse;'>
               <thead>
                 <tr style='border-bottom: 1px solid #ddd;'>
                   <th style='padding: 8px; text-align: left;'>Patient Name</th>
                   <th style='padding: 8px; text-align: left;'>Type</th>
                   <th style='padding: 8px; text-align: left;'>Check In Time</th>
                   <th style='padding: 8px; text-align: left;'>Priority Score</th>
                   <th style='padding: 8px; text-align: left;'>Actions</th>
                  </tr>
               </thead>
                <tbody>
                    """

          for index, row in df.iterrows():
             patient_id = row["id"]
             row_style = ""
             if row['is_checked_in']:
                 row_style = "background-color: green;"

             html_table += f"""
                         <tr style='{row_style} border-bottom: 1px solid #ddd;'>
                           <td style='padding: 8px;'>{row['patient_name']}</td>
                           <td style='padding: 8px;'>{row['type']}</td>
                           <td style='padding: 8px;'>{row['check_in_time'] if row['check_in_time'] else ''}</td>
                           <td style='padding: 8px;'>{row['priority_score']}</td>
                         <td style='padding: 8px;'>
                         <button style='margin-right: 5px; padding: 5px 10px;' onclick="
                           (() => {{
                              Streamlit.setComponentValue(JSON.stringify({{patientId: '{patient_id}', buttonType: 'check_in'}}));
                            }})()
                            ">Check In</button>
                             <button  style='padding: 5px 10px;' onclick="
                                (() => {{
                                    Streamlit.setComponentValue(JSON.stringify({{patientId: '{patient_id}', buttonType: 'done'}}));
                                 }})()
                                ">Done</button>
                            </td>
                          </tr>
                        """
          html_table += "</tbody></table>"

          # Render HTML using st.components.v1.html
          st.components.v1.html(
              f"""
              {html_table}
               <script>
                const elements = document.querySelectorAll("button");
                elements.forEach(function(element) {{
                     element.addEventListener('click', function() {{
                        const value = this.id
                        const data = value.split("_");
                        const buttonType = data[0]
                        const patientId = this.id.split('_')[1]
                        Streamlit.setComponentValue(JSON.stringify({{patientId: patientId, buttonType: buttonType}}))
                        }});
                     }});
                </script>
            """,
              height=400,
              scrolling=True
          )

          selected_value = st.session_state.get("agGrid_key", None)

          if selected_value:
               try:
                   selected_value = json.loads(selected_value)
                   handle_button_click(int(selected_value['patientId']), selected_value['buttonType'])
                   st.session_state["agGrid_key"] = None # Remove key from session state
               except:
                   st.session_state["agGrid_key"] = None
if __name__ == "__main__":
    main()
