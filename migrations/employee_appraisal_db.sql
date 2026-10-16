--
-- PostgreSQL database dump
--

\restrict P9GJfrqCo0sS0mPwUtQoukrvTEOwoXXHkpiczIXpaf63K6i8cq4VSeUSF5PDodq

-- Dumped from database version 18.1
-- Dumped by pg_dump version 18.1

-- Started on 2026-09-07 19:13:05

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 270 (class 1259 OID 17148)
-- Name: appraisal_cycles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.appraisal_cycles (
    cycle_id integer NOT NULL,
    cycle_name character varying(100) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    status character varying(20) DEFAULT 'Active'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_cycle_dates CHECK ((end_date >= start_date)),
    CONSTRAINT valid_cycle_status CHECK (((status)::text = ANY ((ARRAY['Active'::character varying, 'Inactive'::character varying, 'Closed'::character varying])::text[])))
);


ALTER TABLE public.appraisal_cycles OWNER TO postgres;

--
-- TOC entry 269 (class 1259 OID 17147)
-- Name: appraisal_cycles_cycle_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.appraisal_cycles_cycle_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.appraisal_cycles_cycle_id_seq OWNER TO postgres;

--
-- TOC entry 5343 (class 0 OID 0)
-- Dependencies: 269
-- Name: appraisal_cycles_cycle_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.appraisal_cycles_cycle_id_seq OWNED BY public.appraisal_cycles.cycle_id;


--
-- TOC entry 254 (class 1259 OID 16921)
-- Name: attendance; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.attendance (
    attendance_id integer NOT NULL,
    employee_id integer NOT NULL,
    attendance_date date NOT NULL,
    status character varying(20) NOT NULL,
    check_in time without time zone,
    check_out time without time zone,
    late_minutes integer DEFAULT 0,
    overtime_hours numeric(4,2) DEFAULT 0,
    remarks text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT attendance_status_check CHECK (((status)::text = ANY ((ARRAY['Present'::character varying, 'Absent'::character varying, 'Leave'::character varying, 'Holiday'::character varying])::text[])))
);


ALTER TABLE public.attendance OWNER TO postgres;

--
-- TOC entry 253 (class 1259 OID 16920)
-- Name: attendance_attendance_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.attendance_attendance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.attendance_attendance_id_seq OWNER TO postgres;

--
-- TOC entry 5344 (class 0 OID 0)
-- Dependencies: 253
-- Name: attendance_attendance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.attendance_attendance_id_seq OWNED BY public.attendance.attendance_id;


--
-- TOC entry 242 (class 1259 OID 16816)
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.audit_logs (
    log_id integer NOT NULL,
    user_id integer,
    action character varying(100),
    description text,
    ip_address character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.audit_logs OWNER TO postgres;

--
-- TOC entry 241 (class 1259 OID 16815)
-- Name: audit_logs_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.audit_logs_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.audit_logs_log_id_seq OWNER TO postgres;

--
-- TOC entry 5345 (class 0 OID 0)
-- Dependencies: 241
-- Name: audit_logs_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.audit_logs_log_id_seq OWNED BY public.audit_logs.log_id;


--
-- TOC entry 262 (class 1259 OID 17034)
-- Name: behaviour_rating; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.behaviour_rating (
    behaviour_id integer NOT NULL,
    employee_id integer NOT NULL,
    evaluator_id integer NOT NULL,
    appraisal_cycle character varying(100) NOT NULL,
    integrity integer,
    professionalism integer,
    leadership integer,
    accountability integer,
    time_management integer,
    adaptability integer,
    learning_ability integer,
    average_score numeric(4,2),
    remarks text,
    assessment_date date DEFAULT CURRENT_DATE,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT behaviour_rating_accountability_check CHECK (((accountability >= 1) AND (accountability <= 5))),
    CONSTRAINT behaviour_rating_adaptability_check CHECK (((adaptability >= 1) AND (adaptability <= 5))),
    CONSTRAINT behaviour_rating_integrity_check CHECK (((integrity >= 1) AND (integrity <= 5))),
    CONSTRAINT behaviour_rating_leadership_check CHECK (((leadership >= 1) AND (leadership <= 5))),
    CONSTRAINT behaviour_rating_learning_ability_check CHECK (((learning_ability >= 1) AND (learning_ability <= 5))),
    CONSTRAINT behaviour_rating_professionalism_check CHECK (((professionalism >= 1) AND (professionalism <= 5))),
    CONSTRAINT behaviour_rating_time_management_check CHECK (((time_management >= 1) AND (time_management <= 5)))
);


ALTER TABLE public.behaviour_rating OWNER TO postgres;

--
-- TOC entry 261 (class 1259 OID 17033)
-- Name: behaviour_rating_behaviour_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.behaviour_rating_behaviour_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.behaviour_rating_behaviour_id_seq OWNER TO postgres;

--
-- TOC entry 5346 (class 0 OID 0)
-- Dependencies: 261
-- Name: behaviour_rating_behaviour_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.behaviour_rating_behaviour_id_seq OWNED BY public.behaviour_rating.behaviour_id;


--
-- TOC entry 224 (class 1259 OID 16627)
-- Name: branches; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.branches (
    branch_id integer NOT NULL,
    branch_name character varying(100) NOT NULL,
    location character varying(150)
);


ALTER TABLE public.branches OWNER TO postgres;

--
-- TOC entry 223 (class 1259 OID 16626)
-- Name: branches_branch_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.branches_branch_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.branches_branch_id_seq OWNER TO postgres;

--
-- TOC entry 5347 (class 0 OID 0)
-- Dependencies: 223
-- Name: branches_branch_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.branches_branch_id_seq OWNED BY public.branches.branch_id;


--
-- TOC entry 266 (class 1259 OID 17092)
-- Name: certifications; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.certifications (
    certification_id integer NOT NULL,
    employee_id integer NOT NULL,
    certification_name character varying(200) NOT NULL,
    file_name character varying(255) NOT NULL,
    file_path character varying(255) NOT NULL,
    file_type character varying(100),
    issued_date date,
    expiry_date date,
    uploaded_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.certifications OWNER TO postgres;

--
-- TOC entry 265 (class 1259 OID 17091)
-- Name: certifications_certification_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.certifications_certification_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.certifications_certification_id_seq OWNER TO postgres;

--
-- TOC entry 5348 (class 0 OID 0)
-- Dependencies: 265
-- Name: certifications_certification_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.certifications_certification_id_seq OWNED BY public.certifications.certification_id;


--
-- TOC entry 222 (class 1259 OID 16616)
-- Name: departments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.departments (
    department_id integer NOT NULL,
    department_name character varying(100) NOT NULL
);


ALTER TABLE public.departments OWNER TO postgres;

--
-- TOC entry 221 (class 1259 OID 16615)
-- Name: departments_department_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.departments_department_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.departments_department_id_seq OWNER TO postgres;

--
-- TOC entry 5349 (class 0 OID 0)
-- Dependencies: 221
-- Name: departments_department_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.departments_department_id_seq OWNED BY public.departments.department_id;


--
-- TOC entry 226 (class 1259 OID 16636)
-- Name: designations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.designations (
    designation_id integer NOT NULL,
    designation_name character varying(100) NOT NULL
);


ALTER TABLE public.designations OWNER TO postgres;

--
-- TOC entry 225 (class 1259 OID 16635)
-- Name: designations_designation_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.designations_designation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.designations_designation_id_seq OWNER TO postgres;

--
-- TOC entry 5350 (class 0 OID 0)
-- Dependencies: 225
-- Name: designations_designation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.designations_designation_id_seq OWNED BY public.designations.designation_id;


--
-- TOC entry 268 (class 1259 OID 17119)
-- Name: employee_kpi; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.employee_kpi (
    employee_kpi_id integer NOT NULL,
    employee_id integer NOT NULL,
    kpi_id integer NOT NULL,
    assigned_target numeric(12,2),
    appraisal_period character varying(50),
    start_date date,
    end_date date,
    status character varying(20) DEFAULT 'Active'::character varying NOT NULL,
    assigned_by integer,
    assigned_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    cycle_id integer,
    CONSTRAINT employee_kpi_status_check CHECK (((status)::text = ANY ((ARRAY['Active'::character varying, 'Inactive'::character varying, 'Completed'::character varying])::text[])))
);


ALTER TABLE public.employee_kpi OWNER TO postgres;

--
-- TOC entry 267 (class 1259 OID 17118)
-- Name: employee_kpi_employee_kpi_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.employee_kpi_employee_kpi_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.employee_kpi_employee_kpi_id_seq OWNER TO postgres;

--
-- TOC entry 5351 (class 0 OID 0)
-- Dependencies: 267
-- Name: employee_kpi_employee_kpi_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.employee_kpi_employee_kpi_id_seq OWNED BY public.employee_kpi.employee_kpi_id;


--
-- TOC entry 248 (class 1259 OID 16862)
-- Name: employee_kra; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.employee_kra (
    employee_kra_id integer NOT NULL,
    employee_id integer NOT NULL,
    kra_id integer NOT NULL,
    assigned_weightage numeric(5,2) NOT NULL,
    target_value character varying(100),
    due_date date,
    status character varying(20) DEFAULT 'Assigned'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    cycle_id integer
);


ALTER TABLE public.employee_kra OWNER TO postgres;

--
-- TOC entry 247 (class 1259 OID 16861)
-- Name: employee_kra_employee_kra_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.employee_kra_employee_kra_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.employee_kra_employee_kra_id_seq OWNER TO postgres;

--
-- TOC entry 5352 (class 0 OID 0)
-- Dependencies: 247
-- Name: employee_kra_employee_kra_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.employee_kra_employee_kra_id_seq OWNED BY public.employee_kra.employee_kra_id;


--
-- TOC entry 230 (class 1259 OID 16666)
-- Name: employees; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.employees (
    employee_id integer NOT NULL,
    user_id integer,
    employee_code character varying(20) NOT NULL,
    first_name character varying(50) NOT NULL,
    last_name character varying(50) NOT NULL,
    email character varying(100),
    phone character varying(15),
    department_id integer,
    designation_id integer,
    branch_id integer,
    manager_id integer,
    joining_date date,
    employment_status character varying(20) DEFAULT 'Active'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.employees OWNER TO postgres;

--
-- TOC entry 229 (class 1259 OID 16665)
-- Name: employees_employee_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.employees_employee_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.employees_employee_id_seq OWNER TO postgres;

--
-- TOC entry 5353 (class 0 OID 0)
-- Dependencies: 229
-- Name: employees_employee_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.employees_employee_id_seq OWNED BY public.employees.employee_id;


--
-- TOC entry 264 (class 1259 OID 17066)
-- Name: feedback_360; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.feedback_360 (
    feedback_id integer NOT NULL,
    employee_id integer NOT NULL,
    reviewer_id integer,
    appraisal_cycle character varying(20) NOT NULL,
    reviewer_type character varying(20),
    rating integer,
    strengths text,
    improvement_areas text,
    comments text,
    submitted_on date DEFAULT CURRENT_DATE,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT feedback_360_rating_check CHECK (((rating >= 1) AND (rating <= 5))),
    CONSTRAINT feedback_360_reviewer_type_check CHECK (((reviewer_type)::text = ANY ((ARRAY['Manager'::character varying, 'Peer'::character varying, 'Subordinate'::character varying, 'Customer'::character varying])::text[])))
);


ALTER TABLE public.feedback_360 OWNER TO postgres;

--
-- TOC entry 263 (class 1259 OID 17065)
-- Name: feedback_360_feedback_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.feedback_360_feedback_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.feedback_360_feedback_id_seq OWNER TO postgres;

--
-- TOC entry 5354 (class 0 OID 0)
-- Dependencies: 263
-- Name: feedback_360_feedback_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.feedback_360_feedback_id_seq OWNED BY public.feedback_360.feedback_id;


--
-- TOC entry 271 (class 1259 OID 17173)
-- Name: holidays; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.holidays (
    id integer NOT NULL,
    holiday_name character varying(255),
    holiday_date date,
    holiday_type character varying(100),
    status character varying(50)
);


ALTER TABLE public.holidays OWNER TO postgres;

--
-- TOC entry 238 (class 1259 OID 16780)
-- Name: increment_history; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.increment_history (
    increment_id integer NOT NULL,
    employee_id integer NOT NULL,
    previous_salary numeric(10,2),
    increment_amount numeric(10,2),
    new_salary numeric(10,2),
    increment_date date,
    reason text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.increment_history OWNER TO postgres;

--
-- TOC entry 237 (class 1259 OID 16779)
-- Name: increment_history_increment_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.increment_history_increment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.increment_history_increment_id_seq OWNER TO postgres;

--
-- TOC entry 5355 (class 0 OID 0)
-- Dependencies: 237
-- Name: increment_history_increment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.increment_history_increment_id_seq OWNED BY public.increment_history.increment_id;


--
-- TOC entry 250 (class 1259 OID 16885)
-- Name: kpi_master; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.kpi_master (
    kpi_id integer NOT NULL,
    kpi_name character varying(100) NOT NULL,
    description text,
    unit character varying(30),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.kpi_master OWNER TO postgres;

--
-- TOC entry 249 (class 1259 OID 16884)
-- Name: kpi_master_kpi_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.kpi_master_kpi_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.kpi_master_kpi_id_seq OWNER TO postgres;

--
-- TOC entry 5356 (class 0 OID 0)
-- Dependencies: 249
-- Name: kpi_master_kpi_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.kpi_master_kpi_id_seq OWNED BY public.kpi_master.kpi_id;


--
-- TOC entry 252 (class 1259 OID 16897)
-- Name: kpi_records; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.kpi_records (
    employee_kpi_id integer NOT NULL,
    employee_id integer NOT NULL,
    kpi_id integer NOT NULL,
    achieved_value numeric(10,2),
    evaluation_month date NOT NULL,
    remarks text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.kpi_records OWNER TO postgres;

--
-- TOC entry 251 (class 1259 OID 16896)
-- Name: kpi_records_employee_kpi_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.kpi_records_employee_kpi_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.kpi_records_employee_kpi_id_seq OWNER TO postgres;

--
-- TOC entry 5357 (class 0 OID 0)
-- Dependencies: 251
-- Name: kpi_records_employee_kpi_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.kpi_records_employee_kpi_id_seq OWNED BY public.kpi_records.employee_kpi_id;


--
-- TOC entry 246 (class 1259 OID 16849)
-- Name: kra_master; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.kra_master (
    kra_id integer NOT NULL,
    kra_name character varying(100) NOT NULL,
    description text,
    default_weightage numeric(5,2) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.kra_master OWNER TO postgres;

--
-- TOC entry 245 (class 1259 OID 16848)
-- Name: kra_master_kra_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.kra_master_kra_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.kra_master_kra_id_seq OWNER TO postgres;

--
-- TOC entry 5358 (class 0 OID 0)
-- Dependencies: 245
-- Name: kra_master_kra_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.kra_master_kra_id_seq OWNED BY public.kra_master.kra_id;


--
-- TOC entry 256 (class 1259 OID 16945)
-- Name: leave_requests; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.leave_requests (
    leave_id integer NOT NULL,
    employee_id integer NOT NULL,
    leave_type character varying(30) NOT NULL,
    from_date date NOT NULL,
    to_date date NOT NULL,
    number_of_days integer,
    reason text,
    status character varying(20) DEFAULT 'Pending'::character varying,
    approved_by integer,
    applied_on timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT leave_requests_status_check CHECK (((status)::text = ANY ((ARRAY['Pending'::character varying, 'Approved'::character varying, 'Rejected'::character varying])::text[])))
);


ALTER TABLE public.leave_requests OWNER TO postgres;

--
-- TOC entry 255 (class 1259 OID 16944)
-- Name: leave_requests_leave_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.leave_requests_leave_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.leave_requests_leave_id_seq OWNER TO postgres;

--
-- TOC entry 5359 (class 0 OID 0)
-- Dependencies: 255
-- Name: leave_requests_leave_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.leave_requests_leave_id_seq OWNED BY public.leave_requests.leave_id;


--
-- TOC entry 260 (class 1259 OID 16993)
-- Name: manager_appraisal; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.manager_appraisal (
    appraisal_id integer NOT NULL,
    employee_id integer NOT NULL,
    manager_id integer NOT NULL,
    appraisal_cycle character varying(100) NOT NULL,
    productivity numeric(5,2) DEFAULT 0,
    quality_of_work numeric(5,2) DEFAULT 0,
    teamwork numeric(5,2) DEFAULT 0,
    communication numeric(5,2) DEFAULT 0,
    problem_solving numeric(5,2) DEFAULT 0,
    initiative numeric(5,2) DEFAULT 0,
    compliance numeric(5,2) DEFAULT 0,
    total_score numeric(5,2),
    manager_comments text,
    status character varying(20) DEFAULT 'Pending'::character varying,
    appraisal_date date DEFAULT CURRENT_DATE,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT manager_appraisal_communication_check CHECK (((communication >= (0)::numeric) AND (communication <= (10)::numeric))),
    CONSTRAINT manager_appraisal_compliance_check CHECK (((compliance >= (0)::numeric) AND (compliance <= (10)::numeric))),
    CONSTRAINT manager_appraisal_initiative_check CHECK (((initiative >= (0)::numeric) AND (initiative <= (10)::numeric))),
    CONSTRAINT manager_appraisal_problem_solving_check CHECK (((problem_solving >= (0)::numeric) AND (problem_solving <= (10)::numeric))),
    CONSTRAINT manager_appraisal_productivity_check CHECK (((productivity >= (0)::numeric) AND (productivity <= (25)::numeric))),
    CONSTRAINT manager_appraisal_quality_of_work_check CHECK (((quality_of_work >= (0)::numeric) AND (quality_of_work <= (20)::numeric))),
    CONSTRAINT manager_appraisal_status_check CHECK (((status)::text = ANY ((ARRAY['Pending'::character varying, 'Submitted'::character varying, 'Approved'::character varying])::text[]))),
    CONSTRAINT manager_appraisal_teamwork_check CHECK (((teamwork >= (0)::numeric) AND (teamwork <= (15)::numeric)))
);


ALTER TABLE public.manager_appraisal OWNER TO postgres;

--
-- TOC entry 259 (class 1259 OID 16992)
-- Name: manager_appraisal_appraisal_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.manager_appraisal_appraisal_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.manager_appraisal_appraisal_id_seq OWNER TO postgres;

--
-- TOC entry 5360 (class 0 OID 0)
-- Dependencies: 259
-- Name: manager_appraisal_appraisal_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.manager_appraisal_appraisal_id_seq OWNED BY public.manager_appraisal.appraisal_id;


--
-- TOC entry 240 (class 1259 OID 16797)
-- Name: notifications; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.notifications (
    notification_id integer NOT NULL,
    user_id integer,
    title character varying(150) NOT NULL,
    message text NOT NULL,
    notification_type character varying(30),
    is_read boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.notifications OWNER TO postgres;

--
-- TOC entry 239 (class 1259 OID 16796)
-- Name: notifications_notification_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.notifications_notification_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.notifications_notification_id_seq OWNER TO postgres;

--
-- TOC entry 5361 (class 0 OID 0)
-- Dependencies: 239
-- Name: notifications_notification_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.notifications_notification_id_seq OWNED BY public.notifications.notification_id;


--
-- TOC entry 234 (class 1259 OID 16730)
-- Name: performance_result; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.performance_result (
    performance_id integer NOT NULL,
    employee_id integer NOT NULL,
    appraisal_year integer NOT NULL,
    kpi_score numeric(5,2) DEFAULT 0,
    attendance_score numeric(5,2) DEFAULT 0,
    manager_score numeric(5,2) DEFAULT 0,
    behaviour_score numeric(5,2) DEFAULT 0,
    self_appraisal_score numeric(5,2) DEFAULT 0,
    training_score numeric(5,2) DEFAULT 0,
    final_score numeric(5,2) DEFAULT 0,
    rating character varying(50),
    recommendation character varying(255),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.performance_result OWNER TO postgres;

--
-- TOC entry 233 (class 1259 OID 16729)
-- Name: performance_result_performance_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.performance_result_performance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.performance_result_performance_id_seq OWNER TO postgres;

--
-- TOC entry 5362 (class 0 OID 0)
-- Dependencies: 233
-- Name: performance_result_performance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.performance_result_performance_id_seq OWNED BY public.performance_result.performance_id;


--
-- TOC entry 236 (class 1259 OID 16753)
-- Name: promotion_history; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.promotion_history (
    promotion_id integer NOT NULL,
    employee_id integer NOT NULL,
    old_designation_id integer,
    new_designation_id integer,
    promotion_date date,
    reason text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.promotion_history OWNER TO postgres;

--
-- TOC entry 235 (class 1259 OID 16752)
-- Name: promotion_history_promotion_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.promotion_history_promotion_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.promotion_history_promotion_id_seq OWNER TO postgres;

--
-- TOC entry 5363 (class 0 OID 0)
-- Dependencies: 235
-- Name: promotion_history_promotion_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.promotion_history_promotion_id_seq OWNED BY public.promotion_history.promotion_id;


--
-- TOC entry 244 (class 1259 OID 16832)
-- Name: report_history; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.report_history (
    report_id integer NOT NULL,
    generated_by integer,
    report_name character varying(150),
    report_type character varying(50),
    generated_on timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    file_path text
);


ALTER TABLE public.report_history OWNER TO postgres;

--
-- TOC entry 243 (class 1259 OID 16831)
-- Name: report_history_report_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.report_history_report_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.report_history_report_id_seq OWNER TO postgres;

--
-- TOC entry 5364 (class 0 OID 0)
-- Dependencies: 243
-- Name: report_history_report_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.report_history_report_id_seq OWNED BY public.report_history.report_id;


--
-- TOC entry 220 (class 1259 OID 16605)
-- Name: roles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.roles (
    role_id integer NOT NULL,
    role_name character varying(50) NOT NULL
);


ALTER TABLE public.roles OWNER TO postgres;

--
-- TOC entry 219 (class 1259 OID 16604)
-- Name: roles_role_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.roles_role_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.roles_role_id_seq OWNER TO postgres;

--
-- TOC entry 5365 (class 0 OID 0)
-- Dependencies: 219
-- Name: roles_role_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.roles_role_id_seq OWNED BY public.roles.role_id;


--
-- TOC entry 258 (class 1259 OID 16972)
-- Name: self_appraisal; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.self_appraisal (
    self_appraisal_id integer NOT NULL,
    employee_id integer NOT NULL,
    appraisal_cycle character varying(100) NOT NULL,
    achievements text,
    challenges text,
    certifications text,
    training_completed text,
    future_goals text,
    suggestions text,
    submission_status character varying(20) DEFAULT 'Draft'::character varying,
    submitted_on timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT self_appraisal_submission_status_check CHECK (((submission_status)::text = ANY ((ARRAY['Draft'::character varying, 'Submitted'::character varying, 'Reviewed'::character varying])::text[])))
);


ALTER TABLE public.self_appraisal OWNER TO postgres;

--
-- TOC entry 257 (class 1259 OID 16971)
-- Name: self_appraisal_self_appraisal_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.self_appraisal_self_appraisal_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.self_appraisal_self_appraisal_id_seq OWNER TO postgres;

--
-- TOC entry 5366 (class 0 OID 0)
-- Dependencies: 257
-- Name: self_appraisal_self_appraisal_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.self_appraisal_self_appraisal_id_seq OWNED BY public.self_appraisal.self_appraisal_id;


--
-- TOC entry 232 (class 1259 OID 16710)
-- Name: training_records; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.training_records (
    training_id integer NOT NULL,
    employee_id integer NOT NULL,
    training_name character varying(150) NOT NULL,
    training_type character varying(100),
    trainer_name character varying(100),
    start_date date,
    end_date date,
    status character varying(30) DEFAULT 'Pending'::character varying,
    score numeric(5,2),
    certificate_name character varying(255) DEFAULT false,
    remarks text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    certificate_file character varying(255),
    certificate_type character varying(100)
);


ALTER TABLE public.training_records OWNER TO postgres;

--
-- TOC entry 231 (class 1259 OID 16709)
-- Name: training_records_training_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.training_records_training_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.training_records_training_id_seq OWNER TO postgres;

--
-- TOC entry 5367 (class 0 OID 0)
-- Dependencies: 231
-- Name: training_records_training_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.training_records_training_id_seq OWNED BY public.training_records.training_id;


--
-- TOC entry 228 (class 1259 OID 16647)
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    user_id integer NOT NULL,
    username character varying(50) NOT NULL,
    password character varying(255) NOT NULL,
    role_id integer NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.users OWNER TO postgres;

--
-- TOC entry 227 (class 1259 OID 16646)
-- Name: users_user_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_user_id_seq OWNER TO postgres;

--
-- TOC entry 5368 (class 0 OID 0)
-- Dependencies: 227
-- Name: users_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_user_id_seq OWNED BY public.users.user_id;


--
-- TOC entry 5060 (class 2604 OID 17151)
-- Name: appraisal_cycles cycle_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.appraisal_cycles ALTER COLUMN cycle_id SET DEFAULT nextval('public.appraisal_cycles_cycle_id_seq'::regclass);


--
-- TOC entry 5027 (class 2604 OID 16924)
-- Name: attendance attendance_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.attendance ALTER COLUMN attendance_id SET DEFAULT nextval('public.attendance_attendance_id_seq'::regclass);


--
-- TOC entry 5014 (class 2604 OID 16819)
-- Name: audit_logs log_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_logs ALTER COLUMN log_id SET DEFAULT nextval('public.audit_logs_log_id_seq'::regclass);


--
-- TOC entry 5049 (class 2604 OID 17037)
-- Name: behaviour_rating behaviour_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.behaviour_rating ALTER COLUMN behaviour_id SET DEFAULT nextval('public.behaviour_rating_behaviour_id_seq'::regclass);


--
-- TOC entry 4987 (class 2604 OID 16630)
-- Name: branches branch_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.branches ALTER COLUMN branch_id SET DEFAULT nextval('public.branches_branch_id_seq'::regclass);


--
-- TOC entry 5055 (class 2604 OID 17095)
-- Name: certifications certification_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.certifications ALTER COLUMN certification_id SET DEFAULT nextval('public.certifications_certification_id_seq'::regclass);


--
-- TOC entry 4986 (class 2604 OID 16619)
-- Name: departments department_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.departments ALTER COLUMN department_id SET DEFAULT nextval('public.departments_department_id_seq'::regclass);


--
-- TOC entry 4988 (class 2604 OID 16639)
-- Name: designations designation_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.designations ALTER COLUMN designation_id SET DEFAULT nextval('public.designations_designation_id_seq'::regclass);


--
-- TOC entry 5057 (class 2604 OID 17122)
-- Name: employee_kpi employee_kpi_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_kpi ALTER COLUMN employee_kpi_id SET DEFAULT nextval('public.employee_kpi_employee_kpi_id_seq'::regclass);


--
-- TOC entry 5020 (class 2604 OID 16865)
-- Name: employee_kra employee_kra_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_kra ALTER COLUMN employee_kra_id SET DEFAULT nextval('public.employee_kra_employee_kra_id_seq'::regclass);


--
-- TOC entry 4991 (class 2604 OID 16669)
-- Name: employees employee_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees ALTER COLUMN employee_id SET DEFAULT nextval('public.employees_employee_id_seq'::regclass);


--
-- TOC entry 5052 (class 2604 OID 17069)
-- Name: feedback_360 feedback_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feedback_360 ALTER COLUMN feedback_id SET DEFAULT nextval('public.feedback_360_feedback_id_seq'::regclass);


--
-- TOC entry 5009 (class 2604 OID 16783)
-- Name: increment_history increment_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.increment_history ALTER COLUMN increment_id SET DEFAULT nextval('public.increment_history_increment_id_seq'::regclass);


--
-- TOC entry 5023 (class 2604 OID 16888)
-- Name: kpi_master kpi_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kpi_master ALTER COLUMN kpi_id SET DEFAULT nextval('public.kpi_master_kpi_id_seq'::regclass);


--
-- TOC entry 5025 (class 2604 OID 16900)
-- Name: kpi_records employee_kpi_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kpi_records ALTER COLUMN employee_kpi_id SET DEFAULT nextval('public.kpi_records_employee_kpi_id_seq'::regclass);


--
-- TOC entry 5018 (class 2604 OID 16852)
-- Name: kra_master kra_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kra_master ALTER COLUMN kra_id SET DEFAULT nextval('public.kra_master_kra_id_seq'::regclass);


--
-- TOC entry 5031 (class 2604 OID 16948)
-- Name: leave_requests leave_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.leave_requests ALTER COLUMN leave_id SET DEFAULT nextval('public.leave_requests_leave_id_seq'::regclass);


--
-- TOC entry 5038 (class 2604 OID 16996)
-- Name: manager_appraisal appraisal_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.manager_appraisal ALTER COLUMN appraisal_id SET DEFAULT nextval('public.manager_appraisal_appraisal_id_seq'::regclass);


--
-- TOC entry 5011 (class 2604 OID 16800)
-- Name: notifications notification_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notifications ALTER COLUMN notification_id SET DEFAULT nextval('public.notifications_notification_id_seq'::regclass);


--
-- TOC entry 4998 (class 2604 OID 16733)
-- Name: performance_result performance_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.performance_result ALTER COLUMN performance_id SET DEFAULT nextval('public.performance_result_performance_id_seq'::regclass);


--
-- TOC entry 5007 (class 2604 OID 16756)
-- Name: promotion_history promotion_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.promotion_history ALTER COLUMN promotion_id SET DEFAULT nextval('public.promotion_history_promotion_id_seq'::regclass);


--
-- TOC entry 5016 (class 2604 OID 16835)
-- Name: report_history report_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.report_history ALTER COLUMN report_id SET DEFAULT nextval('public.report_history_report_id_seq'::regclass);


--
-- TOC entry 4985 (class 2604 OID 16608)
-- Name: roles role_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.roles ALTER COLUMN role_id SET DEFAULT nextval('public.roles_role_id_seq'::regclass);


--
-- TOC entry 5034 (class 2604 OID 16975)
-- Name: self_appraisal self_appraisal_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.self_appraisal ALTER COLUMN self_appraisal_id SET DEFAULT nextval('public.self_appraisal_self_appraisal_id_seq'::regclass);


--
-- TOC entry 4994 (class 2604 OID 16713)
-- Name: training_records training_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.training_records ALTER COLUMN training_id SET DEFAULT nextval('public.training_records_training_id_seq'::regclass);


--
-- TOC entry 4989 (class 2604 OID 16650)
-- Name: users user_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN user_id SET DEFAULT nextval('public.users_user_id_seq'::regclass);


--
-- TOC entry 5153 (class 2606 OID 17162)
-- Name: appraisal_cycles appraisal_cycles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.appraisal_cycles
    ADD CONSTRAINT appraisal_cycles_pkey PRIMARY KEY (cycle_id);


--
-- TOC entry 5135 (class 2606 OID 16936)
-- Name: attendance attendance_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.attendance
    ADD CONSTRAINT attendance_pkey PRIMARY KEY (attendance_id);


--
-- TOC entry 5123 (class 2606 OID 16825)
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (log_id);


--
-- TOC entry 5145 (class 2606 OID 17054)
-- Name: behaviour_rating behaviour_rating_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.behaviour_rating
    ADD CONSTRAINT behaviour_rating_pkey PRIMARY KEY (behaviour_id);


--
-- TOC entry 5095 (class 2606 OID 16634)
-- Name: branches branches_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.branches
    ADD CONSTRAINT branches_pkey PRIMARY KEY (branch_id);


--
-- TOC entry 5149 (class 2606 OID 17105)
-- Name: certifications certifications_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.certifications
    ADD CONSTRAINT certifications_pkey PRIMARY KEY (certification_id);


--
-- TOC entry 5091 (class 2606 OID 16625)
-- Name: departments departments_department_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_department_name_key UNIQUE (department_name);


--
-- TOC entry 5093 (class 2606 OID 16623)
-- Name: departments departments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_pkey PRIMARY KEY (department_id);


--
-- TOC entry 5097 (class 2606 OID 16645)
-- Name: designations designations_designation_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.designations
    ADD CONSTRAINT designations_designation_name_key UNIQUE (designation_name);


--
-- TOC entry 5099 (class 2606 OID 16643)
-- Name: designations designations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.designations
    ADD CONSTRAINT designations_pkey PRIMARY KEY (designation_id);


--
-- TOC entry 5151 (class 2606 OID 17131)
-- Name: employee_kpi employee_kpi_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_kpi
    ADD CONSTRAINT employee_kpi_pkey PRIMARY KEY (employee_kpi_id);


--
-- TOC entry 5129 (class 2606 OID 16873)
-- Name: employee_kra employee_kra_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_kra
    ADD CONSTRAINT employee_kra_pkey PRIMARY KEY (employee_kra_id);


--
-- TOC entry 5105 (class 2606 OID 16683)
-- Name: employees employees_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_email_key UNIQUE (email);


--
-- TOC entry 5107 (class 2606 OID 16681)
-- Name: employees employees_employee_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_employee_code_key UNIQUE (employee_code);


--
-- TOC entry 5109 (class 2606 OID 16677)
-- Name: employees employees_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_pkey PRIMARY KEY (employee_id);


--
-- TOC entry 5111 (class 2606 OID 16679)
-- Name: employees employees_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_user_id_key UNIQUE (user_id);


--
-- TOC entry 5147 (class 2606 OID 17080)
-- Name: feedback_360 feedback_360_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feedback_360
    ADD CONSTRAINT feedback_360_pkey PRIMARY KEY (feedback_id);


--
-- TOC entry 5155 (class 2606 OID 17178)
-- Name: holidays holidays_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.holidays
    ADD CONSTRAINT holidays_pkey PRIMARY KEY (id);


--
-- TOC entry 5119 (class 2606 OID 16790)
-- Name: increment_history increment_history_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.increment_history
    ADD CONSTRAINT increment_history_pkey PRIMARY KEY (increment_id);


--
-- TOC entry 5131 (class 2606 OID 16895)
-- Name: kpi_master kpi_master_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kpi_master
    ADD CONSTRAINT kpi_master_pkey PRIMARY KEY (kpi_id);


--
-- TOC entry 5133 (class 2606 OID 16909)
-- Name: kpi_records kpi_records_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kpi_records
    ADD CONSTRAINT kpi_records_pkey PRIMARY KEY (employee_kpi_id);


--
-- TOC entry 5127 (class 2606 OID 16860)
-- Name: kra_master kra_master_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kra_master
    ADD CONSTRAINT kra_master_pkey PRIMARY KEY (kra_id);


--
-- TOC entry 5139 (class 2606 OID 16960)
-- Name: leave_requests leave_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.leave_requests
    ADD CONSTRAINT leave_requests_pkey PRIMARY KEY (leave_id);


--
-- TOC entry 5143 (class 2606 OID 17022)
-- Name: manager_appraisal manager_appraisal_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.manager_appraisal
    ADD CONSTRAINT manager_appraisal_pkey PRIMARY KEY (appraisal_id);


--
-- TOC entry 5121 (class 2606 OID 16809)
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (notification_id);


--
-- TOC entry 5115 (class 2606 OID 16746)
-- Name: performance_result performance_result_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.performance_result
    ADD CONSTRAINT performance_result_pkey PRIMARY KEY (performance_id);


--
-- TOC entry 5117 (class 2606 OID 16763)
-- Name: promotion_history promotion_history_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.promotion_history
    ADD CONSTRAINT promotion_history_pkey PRIMARY KEY (promotion_id);


--
-- TOC entry 5125 (class 2606 OID 16841)
-- Name: report_history report_history_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.report_history
    ADD CONSTRAINT report_history_pkey PRIMARY KEY (report_id);


--
-- TOC entry 5087 (class 2606 OID 16612)
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (role_id);


--
-- TOC entry 5089 (class 2606 OID 16614)
-- Name: roles roles_role_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_role_name_key UNIQUE (role_name);


--
-- TOC entry 5141 (class 2606 OID 16986)
-- Name: self_appraisal self_appraisal_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.self_appraisal
    ADD CONSTRAINT self_appraisal_pkey PRIMARY KEY (self_appraisal_id);


--
-- TOC entry 5113 (class 2606 OID 16723)
-- Name: training_records training_records_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.training_records
    ADD CONSTRAINT training_records_pkey PRIMARY KEY (training_id);


--
-- TOC entry 5137 (class 2606 OID 16938)
-- Name: attendance unique_attendance; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.attendance
    ADD CONSTRAINT unique_attendance UNIQUE (employee_id, attendance_date);


--
-- TOC entry 5101 (class 2606 OID 16657)
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- TOC entry 5103 (class 2606 OID 16659)
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- TOC entry 5169 (class 2606 OID 16826)
-- Name: audit_logs audit_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- TOC entry 5176 (class 2606 OID 16939)
-- Name: attendance fk_attendance_employee; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.attendance
    ADD CONSTRAINT fk_attendance_employee FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5182 (class 2606 OID 17055)
-- Name: behaviour_rating fk_behaviour_employee; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.behaviour_rating
    ADD CONSTRAINT fk_behaviour_employee FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5183 (class 2606 OID 17060)
-- Name: behaviour_rating fk_behaviour_evaluator; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.behaviour_rating
    ADD CONSTRAINT fk_behaviour_evaluator FOREIGN KEY (evaluator_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5157 (class 2606 OID 16699)
-- Name: employees fk_branch; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT fk_branch FOREIGN KEY (branch_id) REFERENCES public.branches(branch_id);


--
-- TOC entry 5186 (class 2606 OID 17106)
-- Name: certifications fk_certifications_employee; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.certifications
    ADD CONSTRAINT fk_certifications_employee FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5158 (class 2606 OID 16689)
-- Name: employees fk_department; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT fk_department FOREIGN KEY (department_id) REFERENCES public.departments(department_id);


--
-- TOC entry 5159 (class 2606 OID 16694)
-- Name: employees fk_designation; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT fk_designation FOREIGN KEY (designation_id) REFERENCES public.designations(designation_id);


--
-- TOC entry 5174 (class 2606 OID 16915)
-- Name: kpi_records fk_employee_kpi; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kpi_records
    ADD CONSTRAINT fk_employee_kpi FOREIGN KEY (kpi_id) REFERENCES public.kpi_master(kpi_id) ON DELETE CASCADE;


--
-- TOC entry 5187 (class 2606 OID 17168)
-- Name: employee_kpi fk_employee_kpi_cycle; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_kpi
    ADD CONSTRAINT fk_employee_kpi_cycle FOREIGN KEY (cycle_id) REFERENCES public.appraisal_cycles(cycle_id);


--
-- TOC entry 5188 (class 2606 OID 17132)
-- Name: employee_kpi fk_employee_kpi_employee; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_kpi
    ADD CONSTRAINT fk_employee_kpi_employee FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5175 (class 2606 OID 16910)
-- Name: kpi_records fk_employee_kpi_employee; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.kpi_records
    ADD CONSTRAINT fk_employee_kpi_employee FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5189 (class 2606 OID 17137)
-- Name: employee_kpi fk_employee_kpi_master; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_kpi
    ADD CONSTRAINT fk_employee_kpi_master FOREIGN KEY (kpi_id) REFERENCES public.kpi_master(kpi_id) ON DELETE CASCADE;


--
-- TOC entry 5190 (class 2606 OID 17142)
-- Name: employee_kpi fk_employee_kpi_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_kpi
    ADD CONSTRAINT fk_employee_kpi_user FOREIGN KEY (assigned_by) REFERENCES public.users(user_id) ON DELETE SET NULL;


--
-- TOC entry 5171 (class 2606 OID 16879)
-- Name: employee_kra fk_employee_kra; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_kra
    ADD CONSTRAINT fk_employee_kra FOREIGN KEY (kra_id) REFERENCES public.kra_master(kra_id) ON DELETE CASCADE;


--
-- TOC entry 5172 (class 2606 OID 17163)
-- Name: employee_kra fk_employee_kra_cycle; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_kra
    ADD CONSTRAINT fk_employee_kra_cycle FOREIGN KEY (cycle_id) REFERENCES public.appraisal_cycles(cycle_id);


--
-- TOC entry 5173 (class 2606 OID 16874)
-- Name: employee_kra fk_employee_kra_employee; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employee_kra
    ADD CONSTRAINT fk_employee_kra_employee FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5160 (class 2606 OID 16684)
-- Name: employees fk_employee_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT fk_employee_user FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- TOC entry 5184 (class 2606 OID 17081)
-- Name: feedback_360 fk_feedback_employee; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feedback_360
    ADD CONSTRAINT fk_feedback_employee FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5185 (class 2606 OID 17086)
-- Name: feedback_360 fk_feedback_reviewer; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feedback_360
    ADD CONSTRAINT fk_feedback_reviewer FOREIGN KEY (reviewer_id) REFERENCES public.employees(employee_id) ON DELETE SET NULL;


--
-- TOC entry 5167 (class 2606 OID 16791)
-- Name: increment_history fk_increment_employee; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.increment_history
    ADD CONSTRAINT fk_increment_employee FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5177 (class 2606 OID 16966)
-- Name: leave_requests fk_leave_approver; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.leave_requests
    ADD CONSTRAINT fk_leave_approver FOREIGN KEY (approved_by) REFERENCES public.employees(employee_id) ON DELETE SET NULL;


--
-- TOC entry 5178 (class 2606 OID 16961)
-- Name: leave_requests fk_leave_employee; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.leave_requests
    ADD CONSTRAINT fk_leave_employee FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5161 (class 2606 OID 16704)
-- Name: employees fk_manager; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT fk_manager FOREIGN KEY (manager_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5180 (class 2606 OID 17028)
-- Name: manager_appraisal fk_manager; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.manager_appraisal
    ADD CONSTRAINT fk_manager FOREIGN KEY (manager_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5181 (class 2606 OID 17023)
-- Name: manager_appraisal fk_manager_employee; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.manager_appraisal
    ADD CONSTRAINT fk_manager_employee FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5164 (class 2606 OID 16774)
-- Name: promotion_history fk_new_designation; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.promotion_history
    ADD CONSTRAINT fk_new_designation FOREIGN KEY (new_designation_id) REFERENCES public.designations(designation_id);


--
-- TOC entry 5165 (class 2606 OID 16769)
-- Name: promotion_history fk_old_designation; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.promotion_history
    ADD CONSTRAINT fk_old_designation FOREIGN KEY (old_designation_id) REFERENCES public.designations(designation_id);


--
-- TOC entry 5163 (class 2606 OID 16747)
-- Name: performance_result fk_performance_employee; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.performance_result
    ADD CONSTRAINT fk_performance_employee FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5166 (class 2606 OID 16764)
-- Name: promotion_history fk_promotion_employee; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.promotion_history
    ADD CONSTRAINT fk_promotion_employee FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5179 (class 2606 OID 16987)
-- Name: self_appraisal fk_self_employee; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.self_appraisal
    ADD CONSTRAINT fk_self_employee FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id) ON DELETE CASCADE;


--
-- TOC entry 5162 (class 2606 OID 16724)
-- Name: training_records fk_training_employee; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.training_records
    ADD CONSTRAINT fk_training_employee FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- TOC entry 5156 (class 2606 OID 16660)
-- Name: users fk_user_role; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_user_role FOREIGN KEY (role_id) REFERENCES public.roles(role_id);


--
-- TOC entry 5168 (class 2606 OID 16810)
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- TOC entry 5170 (class 2606 OID 16842)
-- Name: report_history report_history_generated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.report_history
    ADD CONSTRAINT report_history_generated_by_fkey FOREIGN KEY (generated_by) REFERENCES public.users(user_id);


-- Completed on 2026-09-07 19:13:05

--
-- PostgreSQL database dump complete
--

\unrestrict P9GJfrqCo0sS0mPwUtQoukrvTEOwoXXHkpiczIXpaf63K6i8cq4VSeUSF5PDodq

