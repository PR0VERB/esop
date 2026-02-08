RULE FOR PLAIN HTML VS HTMX: USE HTML; ONLY USE HTMX SPARINGLY (WHERE STRICTLY NECESSARY)
TWO MAJOR PROCESSES: 
1. DIVIDEND DISTRIBUTION PROCESS
2. MONTH-END PROCESS

PROCESS 1: DIVIDEND DISTRIBUTION PROCESS
The sequence diagram below is one way to represent the architecture of the dividend 
distribution process. This diagram is not meant to be used as a final guideline, as it embeds 
certain assumptions that are likely incorrect 
Link to enlarged image (download) 
Data Flow 
1. Initial Confirmation: 
● Verify the number of shares held in the Trust and confirm the dividend amount 
received. 
● Obtain results from SENS (Stock Exchange News Service) to validate dividend 
details. 
2. Beneficiary Identification: 
● Request confirmation of scheme shares held in the Trust. 
● Prepare a list of active qualifying beneficiaries eligible for the dividend. 
3. Beneficiary Updates: 
● On the dividend payment date, request an updated list of active qualifying 
beneficiaries. 
● Update the database with the received list. 
4. Dividend Calculation: 
● Calculate the dividend allocation for each beneficiary. 
● Update the final dividend payment upload file. 
5. Payment File Preparation: 
● Calculate after-tax dividend payments for each qualifying beneficiary (those 
active on the Last Date to Trade, LDT). 
● Split dividend payment files into two groups: 
○ Active Beneficiaries 
○ Good/Bad Leavers 
6. Payment Processing: 
● Receive confirmation on the shares and dividend received in the Trust’s bank 
account. 
● Transfer the after-tax dividend payment to the Trust bank account. 
7. Distribution to Beneficiaries: 
● Process the request to pay the after-tax dividend portion to: 
○ Active beneficiaries 
○ Good/Bad Leavers 
● Forward the payment file and proof of dividend payment to complete the process. 
Recommended Solution 
Solution Overview 
Streamline the dividend payment and beneficiary management process, integrating data, 
workflows, and reporting. 
Key Features 
1. Centralised Database: 
○ Store beneficiary details, shareholding data, and tax information securely. 
○ Enable real-time updates for active beneficiaries and transactions. 
2. Workflow Automation: 
○ Automate the dividend calculation process, including gross to after-tax 
calculations. 
○ Streamline beneficiary updates and dividend payment file generation. 
3. System Integrations: 
○ Connect with: 
■ Payroll and HR systems for beneficiary and employee data. 
■ Financial systems for payment processing and tax compliance (e.g., 
SARS directives). 
■ External data sources like SENS for dividend confirmations. 
4. User Dashboard: 
○ Provide stakeholders (finance, payroll, and administrators) with real-time tracking 
of dividend payments, tax filings, and beneficiary updates. 
5. Audit and Compliance: 
○ Maintain an audit trail for all actions (e.g., dividend payments, beneficiary 
changes). 
○ Generate compliance reports for regulatory bodies. 
6. Security and Access Control: 
○ Role-based access control to ensure sensitive data is protected and only 
accessible to authorised personnel. 
Implementation Approach 
1. Understand Stakeholder Needs 
● Confirm system requirements, pain points, and desired outcomes. 
2. Define Key Processes 
● Map workflows: Improve each step from dividend confirmation to payment execution 
and reporting. 
● Identify integration points: Define how data flows between systems (e.g., payroll, trust 
accounts, and tax systems). 
Implementation Timeline  
Phase 1: Database and Automation 
Goal: Create a centralised database and automating core workflows. 
1. Activities: 
○ Database Setup: 
■ Design the schema to store beneficiary details, shareholding data, tax 
records, and transaction history. 
■ Use a relational database for structured data with appropriate indexing for 
fast queries. 
○ Workflow Automation: 
■ Identify repetitive processes (e.g., dividend allocation, beneficiary 
updates, reconciliation). 
■ Implement automation tools like Apache Airflow or Camunda to 
orchestrate workflows. 
■ Can also use tools like n8n or zapier (agent-based) 
■ Build logic for dividend calculations, file splitting, and payment generation. 
○ Security Implementation: 
■ Configure access controls to ensure only authorised users can modify 
sensitive data. 
■ Encrypt sensitive information 
2. Outputs: 
○ A functional database that can handle high volumes of structured data. 
○ Automated workflows for dividend calculation, file generation, and database 
updates. 
3. Challenges: 
○ Ensuring the database design is scalable for future expansion. 
○ Validating workflow logic to ensure calculations are error-free. 
Phase 2: Integrations 
Goal: Connect external systems (e.g., payroll, SARS, banking platforms) with the solution to 
enable real-time data flow. 
1. Activities: 
○ API Development: 
■ Implement APIs for integration with external systems, such as: 
■ Payroll systems: Sync beneficiary data for new hires, terminations, 
and promotions. 
■ SARS: Retrieve tax directives for accurate calculations. 
■ Banking systems: Submit payment files and fetch transaction 
confirmations. 
○ Data Validation: 
■ Build validation rules to ensure data from external sources (e.g., SENS, 
payroll) is accurate and complete before entering the system. 
○ Error Handling: 
■ Add retry mechanisms for failed API calls. 
■ Configure alerts for critical failures or delays in data flow. 
2. Outputs: 
○ Integrated system that communicates in real-time with external platforms. 
○ Robust error-handling mechanisms for all integrations. 
3. Challenges: 
○ Handling discrepancies between external system formats (e.g., payroll data 
structures). 
○ Managing downtime or latency in third-party systems. 
Phase 3: User Interface 
Goal: Build a dashboard 
1. Activities: 
○ Dashboard Design: 
■ Create dashboards for different stakeholder groups: 
■ Executives: High-level overview of dividend payments, compliance 
metrics, and system performance. 
■ Admins: Detailed views of beneficiary data, payment statuses, and 
error logs. 
○ Functionality Development: 
■ Enable real-time status tracking for dividend calculations, payments, and 
tax submissions. 
■ Provide search and filter capabilities for beneficiary and transaction data. 
■ Implement manual override features for administrators to resolve flagged 
issues. 

Phase 4: Testing and Deployment 
Goal: Validate system functionality, accuracy, and reliability before deploying to production. 
1. Activities: 
○ Testing: 
■ Unit Testing: Test individual modules (e.g., dividend calculation logic, API 
integrations). 
■ Integration Testing: Validate end-to-end workflows, including data 
syncing between systems. 
■ Performance Testing: Ensure the system can handle high volumes of 
data and transactions without latency. 
■ User Acceptance Testing: Conduct testing sessions with key 
stakeholders to ensure the system meets business needs. 
○ Bug Fixes: 
■ Address any issues found during testing, ensuring compliance with 
business rules. 
○ Deployment: 
■ Deploy the system in a staging environment for final validation. 
■ Gradually roll out to production using a phased deployment strategy to 
minimise risks. 
○ Monitoring: 
■ Implement monitoring tools to track system performance post-deployment 
(e.g., API response times, error rates). 
2. Outputs: 
○ A tested and stable system deployed in production. 
○ Monitoring dashboards for tracking system health and performance. 
3. Challenges: 
○ Identifying all edge cases during testing to prevent unforeseen issues in 
production. 
○ Managing the rollout to minimise disruption to existing workflows. 
PROCESS 2: MONTH-END PROCESS 
The sequence diagram below is one way to represent the architecture of month-end process. 
This diagram is not meant to be used as a final guideline, as it embeds certain assumptions that 
are likely incorrect. 
Link to enlarged image (download) 
Data Flow 
1. Initial Preparation 
● Deem all vested shares as sold. 
● Compile two files: 
○ Beneficiary Payment Upload File. 
○ Income Tax Payment File (to Harmony's Nedbank account). 
● Upload these files to the Standard Bank platform. 
2. Distribution and Updates 
● Receive income tax payment upload files. 
● Compile allocation notices and distribute them to different business units (BUs). 
● Update: 
○ Database. 
○ Static data. 
○ Follow-up reports (with all movements, such as employee updates and 
transactions). 
3. Employee Changes 
● Generate a Monthly Movement Report covering: 
○ Active employees. 
○ Promotions. 
○ New hires. 
○ Terminations. 
● Handle terminations: 
○ Forfeit allocated units. 
○ Update static data, database, and reconciliation reports. 
4. Share Transactions 
● New Requests: Prepare transaction notices for shares (e.g., selling shares at the day's 
average price). 
● Sell shares in bulk for requested transactions. 
● Receive: 
○ JSE contract notes. 
○ Trade schedules (next day). 
● Update payroll: 
○ Upload income tax for the sold shares. 
○ Pay SARS. 
○ Update IRP5 information. 
5. Reconciliation and Payments 
● Forward proof of income tax payments and upload file details. 
● Pay trade proceeds. 
● Reconcile the Sisonke Trust bank account/statement. 
6. Tax and Reporting 
● Handle tax directives: 
○ Split tax between Mozambique beneficiaries (if applicable). 
○ Manage cases with no tax reference numbers or declined directives from SARS. 
● Update reports, including: 
○ Cheque reconciliation. 
○ General reconciliation. 
7. Other Processes 
● Manage allocation units for “Good Leavers” and “Bad Leavers.” 
● Receive and process control sheets from business units. 
● Receive proceeds and reconcile forward month-end processes. 
Recommended Solution 
Solution Overview 
Improve processes for share transactions, tax compliance, beneficiary management, and 
reconciliation activities 
Key Features 
1. Centralised Database 
● Purpose: Consolidate all data for month-end activities into a single source of truth. 
● Functionality: 
○ Store beneficiary details, shareholding data, taxable benefits, and transaction 
history. 
○ Maintain real-time updates for active, terminated, and promoted employees. 
○ Enable query capabilities for reconciliation, reporting, and audit purposes. 
2. Workflow Automation 
● Purpose: Eliminate manual tasks and ensure consistent execution of month-end 
processes. 
● Functionality: 
○ Automate: 
■ Bulk tax directive submissions to SARS. 
■ File generation for beneficiary payments, income tax uploads, and 
transaction notices. 
■ Reconciliation of trust bank accounts and share sales proceeds. 
○ Automatically update reports, including cheque reconciliation and beneficiary 
data updates. 
○ Generate and distribute allocation notices to relevant business units. 
3. System Integrations 
● Purpose: Ensure seamless data flow across systems and external platforms. 
● Integration Points: 
○ Payroll Systems: 
■ Sync beneficiary data for active employees, terminations, and new 
appointments. 
■ Upload income tax payments and update IRP5 details. 
○ SARS: 
■ Submit bulk tax directive requests and validate compliance with tax 
regulations. 
○ JSE and Velocity Trade: 
■ Automate share sale processing and retrieve trade schedules and 
contract notes. 
○ Banking Platforms: 
■ Upload income tax payments and process share sale proceeds securely. 
4. User Dashboard 
● Purpose: Provide real-time visibility and control for stakeholders. 
● Functionality: 
○ Custom dashboards for: 
■ Finance: Track income tax payments, trade proceeds, and reconciliation 
activities. 
■ Scheme Admin: Monitor beneficiary movements, allocation notices, and 
share sales. 
○ Enable manual overrides for flagged issues / exceptions. 
○ Visualise progress and bottlenecks in the month-end process. 
5. Audit and Compliance 
● Purpose: Ensure transparency and adherence to legal requirements. 
● Functionality: 
○ Maintain audit trails for all transactions and updates (e.g., income tax 
submissions, beneficiary changes). 
○ Generate compliance reports for internal reviews and regulatory submissions. 
○ Identify and resolve discrepancies in tax directives or trade schedules. 
6. Security and Access Control 
● Purpose: Protect sensitive financial and beneficiary data. 
● Functionality: 
○ Role-based access control to restrict data visibility and system functionalities to 
authorised personnel. 
○ Encrypt sensitive data 
Implementation Approach 
1. Understand Stakeholder Needs 
(Same as for Dividend-Distribution Process) 
2. Define Key Processes 
● Map workflows for: 
○ Beneficiary management (e.g., active employees, terminations). 
○ Tax compliance (e.g., bulk SARS submissions, income tax uploads). 
○ Share transactions and reconciliation (e.g., trade schedules, bank 
reconciliations). 
● Identify integration points with external systems (e.g., SARS, JSE). 
Implementation Timeline  
Phase 1: Database and Workflow Automation 
Objective: 
To establish the foundational infrastructure by setting up a database and automating repetitive 
workflows. 
Activities: 
1. Database Setup: 
○ Design a relational database schema to store: 
■ Beneficiary details (e.g., active, terminated, and promoted employees). 
■ Shareholding data and vested share information. 
■ Tax records (e.g., directives, income tax payment history). 
■ Transaction details (e.g., trade schedules, payment files). 
○ Configure indexing for efficient querying and reporting. 
2. Workflow Automation: 
○ Automate key processes, such as: 
■ Bulk tax directive submissions to SARS. 
■ Generation of beneficiary payment upload files and income tax payment 
files. 
■ Reconciliation of trust bank accounts and trade proceeds. 
■ Updating static data, beneficiary records, and reconciliation reports. 
○ Implement tools like Airflow to orchestrate workflows. 
3. Data Validation: 
○ Implement validation logic to ensure data accuracy before being entered into the 
system (e.g., matching beneficiary records against payroll data). 
Deliverables: 
● Ccentralised database. 
● Automated workflows for all repetitive tasks. 
● Validation rules to ensure data accuracy and integrity. 
Challenges: 
● Ensuring scalability of the database to handle growing volumes of beneficiaries and 
transactions. 
● Fine-tuning workflow logic to minimise errors during automation. 
Phase 2: System Integrations 
Objective: 
To establish seamless data flow by integrating external systems and platforms with the 
month-end solution. 
Activities: 
1. Integration with Payroll Systems: 
○ Sync active, terminated, and promoted employee data in real time. 
○ Retrieve payroll information required for income tax calculations and beneficiary 
management. 
2. Integration with SARS: 
○ Automate bulk tax directive submissions and retrieval of directives. 
○ Validate tax compliance through direct API connections. 
3. Integration with JSE and Velocity Trade: 
○ Automate share sale processing by connecting with trade schedules and contract 
notes. 
○ Sync trade proceeds for accurate reconciliation. 
4. Banking Platform Integration: 
○ Automate the submission of income tax payment files to Standard Bank. 
○ Process share sale proceeds and update trust bank accounts. 
Deliverables: 
● System with: 
○ Payroll for employee and beneficiary data. 
○ SARS for tax directives and compliance checks. 
○ JSE and Velocity Trade for share transaction management. 
○ Banking systems for secure fund transfers. 
Challenges: 
● Handling discrepancies between data formats across different systems. 
● Managing API failures or delays during integrations. 
Phase 3: User Interface Development 
Objective: 
To provide stakeholders with a dashboard for real-time tracking, reporting, and control. 
Activities: 
1. Dashboard Design: 
○ Create dashboards tailored to: 
■ Finance Teams: Track income tax payments, trade proceeds, and 
reconciliation activities. 
■ Scheme Admin: Monitor beneficiary movements, allocation notices, and 
share sales. 
■ Executives: View high-level summaries of operational progress and 
compliance metrics. 
2. Feature Development: 
○ Include features for: 
■ Real-time monitoring of workflows (e.g., tax submissions, reconciliations). 
■ Manual overrides for flagged issues /exceptions. 
■ Customisable views to filter and search data. 
3. Responsive Design: 
○ Ensure dashboards are mobile-friendly and accessible on various devices. 
○ Use frontend frameworks like React.js or Angular for scalability. 
Deliverables: 
● Dashboards for stakeholders. 
● Mobile-responsive user interface. 
● Customisable reporting and tracking features. 
Challenges: 
● Balancing simplicity with functionality to cater to diverse user needs. 
● Ensuring fast loading times for large datasets. 
Phase 4: Testing and Deployment 
Objective: 
To validate the system’s accuracy, reliability, and performance before deploying it in production. 
Activities: 
1. Testing: 
○ Unit Testing: Validate individual modules (e.g., dividend calculations, API 
integrations). 
○ Integration Testing: Test end-to-end workflows to ensure seamless data flow 
between systems. 
○ Performance Testing: Evaluate system performance under high transaction 
volumes. 
○ User Acceptance Testing (UAT): Involve key stakeholders to validate the 
system against business requirements. 
2. Bug Fixing: 
○ Resolve issues identified during testing. 
○ Conduct regression testing to ensure fixes do not introduce new issues. 
3. Deployment: 
○ Deploy the system in a staging environment for final validation. 
○ Gradually roll out to production using a phased approach to minimise risks. 
4. Monitoring: 
○ Implement monitoring tools to track system performance (e.g., API response 
times, error rates). 
○ Set up alert mechanisms for critical issues. 
Deliverables: 
● Deployed system. 
● Monitoring dashboards for ongoing performance tracking. 
Challenges: 
● Identifying and resolving edge cases during testing. 
● Managing the transition to minimise disruptions to existing workflows. 
Phase 5: Training and Support 
Objective: 
To ensure users can use the new system and resolve any post-deployment issues. 
Activities: 
1. Training Sessions: 
○ Conduct workshops for Scheme Admin, Finance, and Payroll teams. 
○ Provide hands-on training on dashboards, workflows, and troubleshooting. 
2. Documentation: 
○ Develop user manuals, quick-start guides, and FAQs. 
3. Support Mechanisms: 
○ Set up a dedicated support team to handle user queries and technical issues. 
○ Implement a ticketing system for issue tracking and resolution. 
Deliverables: 
● Trained users across all relevant teams. 
● Documentation for system usage. 
● Responsive support team for post-deployment assistance. 
Phase 6: Monitoring and Optimisation 
Objective: 
To ensure the system operates optimally and evolves with business needs. 
Activities: 
1. Performance Monitoring: 
○ Track KPIs such as processing times, error rates, and system uptime. 
2. Feedback Collection: 
○ Gather user feedback on system usability and performance. 
3. System Optimisation: 
○ improve workflows and features based on feedback and changing requirements. 
○ Address new regulatory or operational needs. 
Deliverables: 
● Regular system updates and optimisations. 
● Improved user experience based on feedback. 
● A future-ready solution capable of scaling with the business. 