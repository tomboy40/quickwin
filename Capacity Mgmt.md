# What is Capacity Management

Capacity Management is a mandatory process of making sure that we always have the right capacity in the right place at the right time for the right cost.

* Right Capacity means we need to ensure that we have sufficient infra to meet business requirements. This is typically measured by ensuring that service can meet defined performance requirement (normally documented as non-functional requirements)  
* Right Place generally refers to the place with the architecture rather than physical location, so in this context, means ensuring that all the layers (app, middleware, db etc.) have the right infra. Care must be taken to ensure that it is properly allocated such ath one layer doesn’t flood another layer with traffic, moving the bottleneck around the different components in the service.  
* Right Time means that we need to ensure that we have sufficient capacity in place before issues occur, or in  time to meet planned business requirements (such as new products, or application migration), We don’t want to have the infra too early or we incur additional costs  
* Right Cost means that we need to ensure that we don’t significantly over-provision just to prevent issues. Excess capacity costs unjustifiable costs in software licencing, power consumption and support

# What are the Benefit of an Effective Capacity Management Process

By having an effective Capacity Management process:

* Improved Service Availability \-the incidents relating to a lack of capacity should be reduced, ideally eliminated  
* Investment Forecasting \- allows investment to be forecast in alignment with planning and budget cycle. It avoid both unplanned investment also ensuring that we don’t have excessive unused capacity  
* Optimizing Infra performance \- helps ensure that infra performance is optimized by monitoring consumption and identifying bottlenecks.   
* Scaling \- potential issues from rapid scaling can be identified and highlighted, allowing remedial action to be taken before service impacting incidents occur.  
* Continual Performance Improvement \- can help drive continual improvement within services by highlighting the next constraints.

# Capacity Management Tool \- Athene

Syncsort Capacity Management (SCM) is the Group Standard Capacity Planning and Performance Management tool set

* SCM is able to take data from variety data source  
* SCN allows the environment to be managed in a far more agile manner than conventional Capacity Management tools. This can be done at a service by server level, using standard reporting dashboard techniques  
* SCM offers predictive analytics that allows forward looking projection to be created. This allows a view on the expected performance of the service in the future  
* Using the power of the predictive analytics in the “Service View” module, when a potential breach is identified the defined support team for that service will receive an alert containing details of what has been identified.

# How are we doing nowadays in MBG

A service view created on Athene is required for service to support Capacity Management process and it identifies potential breach dates to raise alert when a breach is projected. This allows automated alerts to be raised, ensuring that any potential issues are identified with sufficient notice to allow remedial action to be taken before production incident or service failure occurs.  
The operational effectiveness of this control is measured by the use of 4 Key Control Indicators.

# What is the central team going to do?

## Approach

We will establish a Capacity Management Practice Framework (CMPF) to meet expectation consistency and at scale. This will ensure the systematic identification and management of services that are capacity-sensitive 

This practice will leverage the existing capacity management control not in isolation, but in coordination with other critical disciplines such as scenario testing, architecture, and the software development lifecycle.

## Objectives

- Business-aligned capacity management: bring BSOs inputs for growth plans  
- Expanding to include Capacity Management beyond infra including IT Assess level and business business service  
- Enable a consistent practice across Teams  
- Proactive management of capacity-related risks through adequate KPIs and KCIs  
- Improved resource allocation efficiency

## High Level Milestones

1. May \- Jul 2025  
   1. Capacity Management Framework (including Architecture, application, business services)  
   2. BSOs capacity assessment results for stress (headroom capacity)  
2. Sep 2025:: Foundations for the practice & controls  
   1. Teams playbooks & adoption plans  
   2. Practice interlocks and tooling review  
   3. Control Redesign (Procedures, Operating instructions, KCIs)  
3. Jan \- Feb 2026: Targeted Adoption  
   1. Teams prioritised adoption  
   2. Control uplift  
4. Jun \- Dec  2026: Practice sustainability / Control effectiveness  
   1. Teams scaled adoption / Control Effectiveness

## Milestones (definition of done)

| Milestone ID | Title | Milestone | Pre-requisites | High Level Activities | Definition of Done (Success Criteria) | Next Step | Due Date | Action Required | Owner |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| M001 | PoC Access to case | Gathering Business requirements Workload profiling Outcomes of last known testing | (Central team) Provide list of in-scope services, capture template & Capacity Management Change Framework | Feedback on the questionnaire to build a bottom-up view (Task Force SME) Support/oversight of the completion of the questionnaire, for services under your remit | Gathering Business requirements Workload profiling Outcomes of last known testing | 2-3 working days over 2-week period | 11-July-2025 | Pilot Execution | Capacity Management PM |
| M002 | Production Stability \- residual tail | List of BPS (Business Prioritized Services) SaaS for upload to Capacity Management Assessment Tool (CMA) | Production Stability & Capacity Management PM) Provide a list of BPS that require SaaS flag in CMA and the last stress test date | (Central team) Bulk upload data to CMA | (Prod stability PM) SaaS flag data provided (Prod stability PM) Last stress test date provided Remediation & Adoption plan updated (Stress test inline with SDLC testing requirement) |  | 30-July-2025 | Execution & Reporting / Oversight | Prod stability PM |
| M003 | Capacity Management Playbook & Adoption plans | Each team will deliver playbooks to implement the capacity management practices (defined in the CMPF framework). Also, each teams will deliver an adoption plan for Import IT Asset (IITA) supporting UK, Important Business Service (IBS) and HK Critical Operations (HK CO), subject to demand peaks | (Central Team) Definition & template of “Playbook” including guidance/instructions, at both IBS/HK CO service chain and IITA level | Project plan, to harvest existing playbooks with associated, gaps as part of an inventory Gaps form remediation plan(s) | Inventory of playbooks by team  inc any gaps (missing info \- inline with playbook template) Remediation & adoption plan updated | Planning & Estimation | 30-Sept-2025 | Inventory & gap analysis | Capacity Management PM |
| M004 | Capacity Management Control redesign pilot | Capacity Management will update Mandatory Procedures, Operating Instructions, Global Risk Appetite Statement (GRAS), Key Control Indicators (KCI), as part of a pilot, to align with Capacity Management Framework | Capacity Management Practices Framework Core Capabilities Control procedure updated, aligned to latest Capacity Management Practice Framework inc GRAS & KCI proposed redesign Pilot success criteria provided by Central team, accepted by task forces | In consultation with SME select services subject to demand peaks, to adopt both Capacity Management Control Operating Procedures & Core Capabilities as part of the Capacity management Practice Framework Gaps form remediation plan | Pilot success criteria met Remediation & Adoption plan updated | Planning & Estimation | 30-Sept-2025 | Pilot Execution | Capacity Management PM |
| M005 | Capacity Management Uplift for UK IDS and HK CO | Capacity Management will implement Business capacity management, capacity testing practices and observability & reporting for IBS and HK CO, subject to demand peaks | Lessons learned feedback loop from “Pilots”, “Playbook” inventory & “playbooks”, updated capacity management Control operating procedures & Capacity management Practices Framework (CMPF) Completion of milestones (M003 and M004) | Remaining IITA/IBS/HK CO to adopt both Capacity Management Controls Mandatory procedures, Operating Instructions & Core capabilities (People, Process & Tooling) as part of the Capability Management Practices Framework Gaps form remediation plan | Playbook Inventory updated inc associated adoption of Core Capabilities with status of adoption of Capability management control Mandatory procedures, Operating Instructions & Core capabilities (People, process and Tooling) as part of Capacity Management Practice Remediation & Adoption plan updated | Planning & Estimation | 30-Jan-2026 |  |  |
| M006 | Capacity core capabilities in place for IDS and HK CO  | Capacity management capabilities are in place for UK IBS, IBS and HK CO |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |

## Milestones (definition of done) inc 2026 Planning

| Milestone ID | Title | Milestone | Pre-requisites | High Level Activities | Definition of Done (Success Criteria) | Next Step | Due Date | 2026 T-Shirt Size Cost Profile Working Principles |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| M005 | Capacity Management Uplift for UK IDS and HK CO | Capacity Management will implement Business capacity management, capacity testing practices and observability & reporting for IBS and HK CO, subject to demand peaks | Lessons learned feedback loop from “Pilots”, “Playbook” inventory & “playbooks”, updated capacity management Control operating procedures & Capacity management Practices Framework (CMPF) Completion of milestones (M003 and M004) | Remaining IITA/IBS/HK CO to adopt both Capacity Management Controls Mandatory procedures, Operating Instructions & Core capabilities (People, Process & Tooling) as part of the Capability Management Practices Framework Gaps form remediation plan | Playbook Inventory updated inc associated adoption of Core Capabilities with status of adoption of Capability management control Mandatory procedures, Operating Instructions & Core capabilities (People, process and Tooling) as part of Capacity Management Practice Remediation & Adoption plan updated | Planning & Estimation | 30-Jan-2026 | Funding 12 months 1 Capacity Management PM (full or part time) 12 months Capacity Management SME (full or part time) Capacity Adoption & BPS Scaled Adoption ITSO and engineering team to adopt new capabilities Capacity Management Control redesigned Control embedding & adoption Tooling ITSO & Engineering teams: Integration, adoption, testing & deployment of the existing or new tooling (Performance & Stress test and observability) |
| M006 | Capacity core capabilities in place for IDS and HK CO  | Capacity management capabilities are in place for UK IBS, IBS and HK CO |  |  |  |  |  |  |
| M007 | Capacity Management Control Uplift | Capacity Management will implement the revised Mandatory procedures, Operating Instructions, GRAS, KCI to align with CMPF | Baselined Capacity Management Control Mandatory procedures & Operating instructions | Procedures & Mandatory Operating instructions with associated training & comms collateral New L1 GRAS and L2 KCIs live (automate where possible) | COmms, awareness & training implementation plan & execution of the plan to Business Service Owner (BSO), IT service owner (ITSO) and local committees, forums and boards (expand as appropriate) Remediation plan updated Provide data to enable GRAS & KCI reporting (it not yet automated) New GRAS and KCI report, demonstrating compliance & risk position | Planning & Estimation | 27-Feb-2026 |  |

## Capacity Management Practices Framework

## Notes

* Practice outline will be articulated in to CMPF (guidelines, standards, mandatory requirement, RACI)  
* Framework will be contextualised by department and specific guideline will be reflected in the playbooks (“how-to” guide, what to do and when)  
* Framework will be actioned through supporting practices, processes and tooling such as SDLC, NFRs and Incident management process  
* Departments will adopt the CMPF using their playbooks  
* Leveraging Control Operation, tooling and reporting uplift, supported by enhanced governance, tooling, clearer roles and responsibilities and refreshed KCIs

