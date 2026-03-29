import type {Jurisdiction} from "./jurisdictions";

export const SAMPLE_QUESTIONS: Record<Jurisdiction, string[]> = {
    all: [
        "What is the limitation period for a contract claim under DIFC Law No. 5 of 2005?",
        "What are the obligations of a data controller under the GDPR?",
        "What fiduciary duties does a director owe to a company under the Companies Act 2006?",
        "What are the pleading requirements under Federal Rule of Civil Procedure 8?",
        "What are the director duties under the Corporations Act 2001 (Cth)?",
    ],
    difc: [
        "What is the limitation period for a contract claim under DIFC Law No. 5 of 2005?",
        "On what grounds may an employer lawfully terminate an employee under the DIFC Employment Law?",
        "What fiduciary duties does a director owe to a company under the DIFC Companies Law?",
        "How does a party initiate arbitration proceedings under the DIFC Arbitration Law No. 1 of 2008?",
        "What are the essential elements of a valid contract under DIFC Contract Law No. 6 of 2004?",
    ],
    cz: [
        "What are the grounds for termination of employment under Czech labour law?",
        "How is liability for defective products regulated in Czech civil law?",
        "What are the requirements for forming a limited liability company under Czech law?",
        "What constitutes unjust enrichment under the Czech Civil Code?",
        "What are the rules for inheritance under Czech succession law?",
    ],
    eu: [
        "What are the obligations of a data controller under the GDPR?",
        "What constitutes an abuse of dominant position under Article 102 TFEU?",
        "How does the Brussels I Recast Regulation determine jurisdiction in cross-border disputes?",
        "What are the merger control thresholds under the EU Merger Regulation?",
        "What rights does a data subject have regarding automated decision-making under the GDPR?",
    ],
    uk: [
        "What are the statutory duties of a company director under the Companies Act 2006?",
        "What terms are implied in a consumer contract for goods under the Consumer Rights Act 2015?",
        "How are damages assessed for breach of contract under English law?",
        "What are the procedural requirements for issuing a Part 7 claim under the Civil Procedure Rules?",
        "What constitutes wrongful dismissal under the Employment Rights Act 1996?",
    ],
    us: [
        "What are the fiduciary duties of directors under Delaware General Corporation Law?",
        "What warranties are implied in the sale of goods under UCC Article 2?",
        "What are the pleading requirements under Federal Rule of Civil Procedure 8?",
        "What constitutes securities fraud under Section 10(b) of the Securities Exchange Act?",
        "How does the business judgment rule protect corporate directors in Delaware?",
    ],
    au: [
        "What are the director duties under the Corporations Act 2001 (Cth)?",
        "What constitutes unconscionable conduct under the Australian Consumer Law?",
        "How is contributory negligence assessed under Australian tort law?",
        "What are the elements of a criminal charge for assault under Australian common law?",
        "What disclosure obligations apply to financial services licensees under the Corporations Act?",
    ],
    custom: [
        "What is the limitation period for a contract claim?",
        "What are the grounds for termination of employment?",
        "What fiduciary duties does a director owe to a company?",
        "How is liability for defective products regulated?",
        "What constitutes unjust enrichment?",
    ],
};
