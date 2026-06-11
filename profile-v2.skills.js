// profile-v2.skills.js — Skills with Catalog Autocomplete + Custom Skills (Phase 1)
// Depends on: profile-v2.state.js, profile-v2.api.js, profile-v2.utils.js

(function(){
  var overlay   = document.getElementById('skillOverlay');
  var saveBtn   = document.getElementById('skillSaveBtn');
  var cancelBtn = document.getElementById('skillCancelBtn');
  var closeBtn  = document.getElementById('skillClose');
  if(!overlay || !saveBtn) return;

  function f(id){ return document.getElementById(id); }
  function fv(id){ return ((f(id)||{}).value||'').trim(); }
  function sv(id,v){ var el=f(id); if(el) el.value=(v==null?'':v); }

  // ── Skill Catalog (Phase 1 — embedded; Phase 2 moves to DB) ──
  // Format: {slug, en, ar, kw}
  // The catalog is expandable — custom skills not in this list are allowed with a "مخصصة" badge.
  var CATALOG = [
    // ── Programming Languages ──
    {slug:'javascript',en:'JavaScript',ar:'جافا سكريبت',kw:'js جافاسكريبت web'},
    {slug:'python',en:'Python',ar:'بايثون',kw:'بايثون py'},
    {slug:'java',en:'Java',ar:'جافا',kw:'جافا oop'},
    {slug:'typescript',en:'TypeScript',ar:'تايب سكريبت',kw:'ts'},
    {slug:'cpp',en:'C++',ar:'سي بلس بلس',kw:'cpp سي بلس'},
    {slug:'csharp',en:'C#',ar:'سي شارب',kw:'dotnet سي شارب'},
    {slug:'php',en:'PHP',ar:'PHP',kw:'لارافيل'},
    {slug:'swift',en:'Swift',ar:'سويفت',kw:'ios apple'},
    {slug:'kotlin',en:'Kotlin',ar:'كوتلن',kw:'android'},
    {slug:'go',en:'Go',ar:'Go',kw:'golang'},
    {slug:'ruby',en:'Ruby',ar:'روبي',kw:'rails'},
    {slug:'r_lang',en:'R',ar:'R',kw:'r language احصاء statistics'},
    {slug:'dart',en:'Dart',ar:'دارت',kw:'flutter'},
    {slug:'scala',en:'Scala',ar:'سكالا',kw:''},
    {slug:'rust',en:'Rust',ar:'رست',kw:''},
    {slug:'matlab',en:'MATLAB',ar:'ماتلاب',kw:'simulation محاكاة'},
    {slug:'vba',en:'VBA',ar:'VBA',kw:'excel macro اكسل ماكرو'},
    {slug:'bash',en:'Bash / Shell Script',ar:'باش / سكريبت',kw:'bash shell script linux'},
    {slug:'perl',en:'Perl',ar:'Perl',kw:'perl scripting'},
    {slug:'lua',en:'Lua',ar:'لوا',kw:'lua game'},
    {slug:'solidity',en:'Solidity',ar:'سوليديتي',kw:'blockchain web3 ethereum'},
    {slug:'assembly',en:'Assembly',ar:'أسمبلي',kw:'asm assembly low-level'},
    // ── Web Frontend ──
    {slug:'html',en:'HTML',ar:'HTML',kw:'html5 markup'},
    {slug:'css',en:'CSS',ar:'CSS',kw:'css3 styling'},
    {slug:'react',en:'React',ar:'رياكت',kw:'reactjs'},
    {slug:'vuejs',en:'Vue.js',ar:'فيو',kw:'vue vuejs'},
    {slug:'angular',en:'Angular',ar:'أنغولار',kw:'angularjs'},
    {slug:'nextjs',en:'Next.js',ar:'نكست',kw:'nextjs'},
    {slug:'nuxtjs',en:'Nuxt.js',ar:'نكست فيو',kw:'nuxt'},
    {slug:'bootstrap',en:'Bootstrap',ar:'بوتستراب',kw:'css framework'},
    {slug:'tailwind',en:'Tailwind CSS',ar:'تيلويند',kw:'tailwindcss'},
    {slug:'jquery',en:'jQuery',ar:'jQuery',kw:'js library'},
    {slug:'svelte',en:'Svelte',ar:'سفيلت',kw:'svelte frontend'},
    {slug:'redux',en:'Redux',ar:'ريدكس',kw:'redux state management'},
    {slug:'graphql',en:'GraphQL',ar:'GraphQL',kw:'graphql api query'},
    {slug:'webpack',en:'Webpack',ar:'ويب باك',kw:'webpack bundler build'},
    {slug:'vite',en:'Vite',ar:'فيت',kw:'vite build tool frontend'},
    // ── Backend Frameworks ──
    {slug:'nodejs',en:'Node.js',ar:'نود',kw:'nodejs node express'},
    {slug:'django',en:'Django',ar:'دجانغو',kw:'python framework'},
    {slug:'flask',en:'Flask',ar:'فلاسك',kw:'python flask'},
    {slug:'fastapi',en:'FastAPI',ar:'FastAPI',kw:'python api'},
    {slug:'laravel',en:'Laravel',ar:'لارافيل',kw:'php'},
    {slug:'springboot',en:'Spring Boot',ar:'سبرينغ',kw:'spring java framework'},
    {slug:'aspnet',en:'ASP.NET',ar:'ASP.NET',kw:'dotnet csharp'},
    {slug:'expressjs',en:'Express.js',ar:'إكسبريس',kw:'nodejs express'},
    {slug:'nestjs',en:'NestJS',ar:'نست',kw:'nestjs nodejs typescript'},
    {slug:'rails',en:'Ruby on Rails',ar:'روبي أون ريلز',kw:'rails ruby framework'},
    {slug:'rest_api',en:'REST API',ar:'REST API',kw:'rest api web services'},
    // ── Mobile ──
    {slug:'react_native',en:'React Native',ar:'ريأكت نيتف',kw:'mobile cross platform'},
    {slug:'flutter',en:'Flutter',ar:'فلاتر',kw:'dart mobile'},
    {slug:'android_dev',en:'Android Development',ar:'تطوير أندرويد',kw:'android kotlin java mobile'},
    {slug:'ios_dev',en:'iOS Development',ar:'تطوير iOS',kw:'ios swift apple'},
    // ── Databases ──
    {slug:'sql',en:'SQL',ar:'إس كيو إل',kw:'قواعد بيانات database استعلامات'},
    {slug:'mysql',en:'MySQL',ar:'ماي إس كيو إل',kw:'mysql database'},
    {slug:'postgresql',en:'PostgreSQL',ar:'بوستغريس',kw:'postgres postgresql'},
    {slug:'mongodb',en:'MongoDB',ar:'مونغو',kw:'nosql mongodb'},
    {slug:'oracle_db',en:'Oracle Database',ar:'أوراكل',kw:'oracle plsql'},
    {slug:'redis',en:'Redis',ar:'ريديس',kw:'redis cache'},
    {slug:'firebase',en:'Firebase',ar:'فايربيز',kw:'firebase google'},
    {slug:'sqlite',en:'SQLite',ar:'إس كيو لايت',kw:'sqlite local'},
    {slug:'elasticsearch',en:'Elasticsearch',ar:'إلاستيك سيرش',kw:'elastic search'},
    {slug:'mariadb',en:'MariaDB',ar:'ماريا دي بي',kw:'mariadb mysql'},
    {slug:'dynamodb',en:'DynamoDB',ar:'دينامو دي بي',kw:'dynamodb aws nosql'},
    {slug:'cassandra',en:'Cassandra',ar:'كاساندرا',kw:'cassandra nosql'},
    {slug:'supabase',en:'Supabase',ar:'سوبابيس',kw:'supabase postgres'},
    // ── Cloud / DevOps ──
    {slug:'docker',en:'Docker',ar:'دوكر',kw:'docker containers'},
    {slug:'kubernetes',en:'Kubernetes',ar:'كوبيرنيتس',kw:'k8s orchestration'},
    {slug:'aws',en:'AWS',ar:'أمازون كلاود',kw:'amazon aws cloud'},
    {slug:'azure',en:'Microsoft Azure',ar:'أزور',kw:'azure microsoft cloud'},
    {slug:'gcp',en:'Google Cloud',ar:'جوجل كلاود',kw:'gcp google cloud'},
    {slug:'git',en:'Git',ar:'جيت',kw:'git github gitlab version control'},
    {slug:'linux',en:'Linux',ar:'لينكس',kw:'linux ubuntu bash terminal'},
    {slug:'cicd',en:'CI/CD',ar:'CI/CD',kw:'devops cicd jenkins github actions'},
    {slug:'terraform',en:'Terraform',ar:'تيرافورم',kw:'terraform iac infrastructure'},
    {slug:'nginx',en:'Nginx',ar:'إنجينكس',kw:'nginx web server'},
    {slug:'ansible',en:'Ansible',ar:'أنسيبل',kw:'ansible automation devops'},
    {slug:'jenkins',en:'Jenkins',ar:'جينكنز',kw:'jenkins ci pipeline'},
    {slug:'helm',en:'Helm',ar:'هيلم',kw:'helm kubernetes charts'},
    {slug:'github_actions',en:'GitHub Actions',ar:'GitHub Actions',kw:'github actions workflow'},
    // ── Design ──
    {slug:'photoshop',en:'Adobe Photoshop',ar:'فوتوشوب',kw:'photoshop ps تصميم'},
    {slug:'illustrator',en:'Adobe Illustrator',ar:'إليستريتور',kw:'illustrator ai vector'},
    {slug:'figma',en:'Figma',ar:'فيغما',kw:'figma ui prototype تصميم'},
    {slug:'xd',en:'Adobe XD',ar:'أدوبي XD',kw:'xd ux wireframe'},
    {slug:'premiere',en:'Adobe Premiere',ar:'بريمير',kw:'premiere video editing تحرير فيديو'},
    {slug:'aftereffects',en:'Adobe After Effects',ar:'أفتر إفيكتس',kw:'after effects motion animation'},
    {slug:'ui_design',en:'UI Design',ar:'تصميم الواجهات',kw:'ui user interface تصميم'},
    {slug:'ux_design',en:'UX Design',ar:'تجربة المستخدم',kw:'ux user experience usability'},
    {slug:'graphic_design',en:'Graphic Design',ar:'تصميم جرافيك',kw:'graphic جرافيك design'},
    {slug:'autocad',en:'AutoCAD',ar:'أوتوكاد',kw:'autocad cad هندسة'},
    {slug:'three_d',en:'3D Modeling',ar:'نمذجة ثلاثية الأبعاد',kw:'3d blender modeling'},
    {slug:'motion_graphics',en:'Motion Graphics',ar:'موشن جرافيك',kw:'motion graphics animation موشن'},
    {slug:'logo_design',en:'Logo Design',ar:'تصميم الشعارات',kw:'logo design شعار'},
    {slug:'brand_identity',en:'Brand Identity',ar:'الهوية البصرية',kw:'brand identity هوية بصرية'},
    {slug:'canva',en:'Canva',ar:'كانفا',kw:'canva design تصميم'},
    {slug:'davinci',en:'DaVinci Resolve',ar:'دافنشي',kw:'davinci video editing montage'},
    {slug:'indesign',en:'Adobe InDesign',ar:'إن ديزاين',kw:'indesign print layout'},
    {slug:'sketch_design',en:'Sketch',ar:'سكتش',kw:'sketch ui design mac'},
    {slug:'social_media_design',en:'Social Media Design',ar:'تصميم السوشيال ميديا',kw:'social media design post'},
    // ── Office / Productivity ──
    {slug:'excel',en:'Microsoft Excel',ar:'إكسل',kw:'excel spreadsheet جداول بيانات'},
    {slug:'word',en:'Microsoft Word',ar:'وورد',kw:'word document وورد'},
    {slug:'powerpoint',en:'Microsoft PowerPoint',ar:'باوربوينت',kw:'powerpoint presentation عروض'},
    {slug:'access',en:'Microsoft Access',ar:'أكسس',kw:'access microsoft'},
    {slug:'ms_office',en:'Microsoft Office',ar:'مايكروسوفت أوفيس',kw:'office أوفيس'},
    {slug:'google_sheets',en:'Google Sheets',ar:'جوجل شيتس',kw:'sheets google docs'},
    {slug:'google_workspace',en:'Google Workspace',ar:'جوجل ورك سبيس',kw:'google drive gmail docs'},
    {slug:'data_entry',en:'Data Entry',ar:'إدخال البيانات',kw:'data entry إدخال بيانات typing'},
    {slug:'jira',en:'Jira',ar:'جيرا',kw:'jira project management agile'},
    {slug:'trello',en:'Trello',ar:'تريلو',kw:'trello kanban project'},
    {slug:'notion',en:'Notion',ar:'نوشن',kw:'notion workspace productivity'},
    // ── Management / Soft Skills (General) ──
    {slug:'project_management',en:'Project Management',ar:'إدارة المشاريع',kw:'pm pmp إدارة مشاريع'},
    {slug:'agile',en:'Agile / Scrum',ar:'أجايل / سكرام',kw:'agile scrum sprint kanban'},
    {slug:'team_leadership',en:'Team Leadership',ar:'قيادة الفريق',kw:'leadership قيادة فريق'},
    {slug:'communication',en:'Communication Skills',ar:'مهارات التواصل',kw:'communication تواصل presentation'},
    {slug:'problem_solving',en:'Problem Solving',ar:'حل المشكلات',kw:'problem solving analytical تحليل'},
    {slug:'time_management',en:'Time Management',ar:'إدارة الوقت',kw:'time management productivity وقت'},
    {slug:'critical_thinking',en:'Critical Thinking',ar:'التفكير النقدي',kw:'critical thinking تفكير نقدي'},
    {slug:'strategic_planning',en:'Strategic Planning',ar:'التخطيط الاستراتيجي',kw:'strategic planning تخطيط استراتيجي'},
    {slug:'operations_mgmt',en:'Operations Management',ar:'إدارة العمليات',kw:'operations management عمليات'},
    {slug:'change_management',en:'Change Management',ar:'إدارة التغيير',kw:'change management تغيير'},
    {slug:'business_analysis',en:'Business Analysis',ar:'تحليل الأعمال',kw:'business analysis تحليل أعمال'},
    {slug:'business_dev',en:'Business Development',ar:'تطوير الأعمال',kw:'business development تطوير'},
    {slug:'okr',en:'OKR',ar:'OKR',kw:'okr goals objectives'},
    {slug:'kpi',en:'KPIs',ar:'مؤشرات الأداء',kw:'kpi performance indicators أداء'},
    {slug:'process_improvement',en:'Process Improvement',ar:'تحسين العمليات',kw:'process improvement lean'},
    // ── Business / Marketing ──
    {slug:'marketing',en:'Marketing',ar:'تسويق',kw:'marketing digital تسويق رقمي'},
    {slug:'seo',en:'SEO',ar:'تحسين محركات البحث',kw:'seo search engine تحسين'},
    {slug:'social_media',en:'Social Media Marketing',ar:'تسويق التواصل الاجتماعي',kw:'social media instagram twitter تواصل'},
    {slug:'content_writing',en:'Content Writing',ar:'كتابة المحتوى',kw:'content copywriting كتابة محتوى'},
    {slug:'email_marketing',en:'Email Marketing',ar:'تسويق البريد الإلكتروني',kw:'email marketing newsletter'},
    {slug:'google_ads',en:'Google Ads',ar:'إعلانات جوجل',kw:'google ads ppc sem'},
    {slug:'facebook_ads',en:'Facebook Ads',ar:'إعلانات فيسبوك',kw:'facebook ads meta social'},
    {slug:'google_analytics',en:'Google Analytics',ar:'جوجل أناليتيكس',kw:'google analytics tracking'},
    {slug:'brand_management',en:'Brand Management',ar:'إدارة العلامات التجارية',kw:'brand management علامة تجارية'},
    {slug:'market_research',en:'Market Research',ar:'بحث السوق',kw:'market research بحث سوق'},
    {slug:'public_relations',en:'Public Relations',ar:'العلاقات العامة',kw:'pr public relations علاقات عامة'},
    {slug:'influencer_mkt',en:'Influencer Marketing',ar:'التسويق عبر المؤثرين',kw:'influencer marketing مؤثرين'},
    {slug:'affiliate_mkt',en:'Affiliate Marketing',ar:'التسويق بالعمولة',kw:'affiliate marketing عمولة'},
    {slug:'hubspot',en:'HubSpot',ar:'هب سبوت',kw:'hubspot crm marketing'},
    {slug:'crm_tools',en:'CRM',ar:'إدارة علاقات العملاء',kw:'crm salesforce hubspot'},
    {slug:'salesforce',en:'Salesforce',ar:'سيلز فورس',kw:'salesforce crm sales'},
    // ── Sales ──
    {slug:'sales',en:'Sales',ar:'المبيعات',kw:'sales selling مبيعات'},
    {slug:'b2b_sales',en:'B2B Sales',ar:'مبيعات B2B',kw:'b2b sales business'},
    {slug:'b2c_sales',en:'B2C Sales',ar:'مبيعات B2C',kw:'b2c sales consumer retail'},
    {slug:'negotiation',en:'Negotiation',ar:'التفاوض',kw:'negotiation تفاوض مفاوضة'},
    {slug:'cold_calling',en:'Cold Calling',ar:'المكالمات الباردة',kw:'cold calling telemarketing'},
    {slug:'sales_strategy',en:'Sales Strategy',ar:'استراتيجية المبيعات',kw:'sales strategy خطة مبيعات'},
    {slug:'retail_sales',en:'Retail Sales',ar:'مبيعات التجزئة',kw:'retail sales تجزئة'},
    {slug:'telesales',en:'Telesales',ar:'مبيعات هاتفية',kw:'telesales phone sales'},
    {slug:'account_management',en:'Account Management',ar:'إدارة الحسابات',kw:'account management key accounts'},
    // ── Accounting & Finance ──
    {slug:'accounting',en:'Accounting',ar:'محاسبة',kw:'accounting محاسبة ميزانية'},
    {slug:'financial_analysis',en:'Financial Analysis',ar:'تحليل مالي',kw:'finance financial مالي'},
    {slug:'bookkeeping',en:'Bookkeeping',ar:'مسك الدفاتر',kw:'bookkeeping دفاتر محاسبة'},
    {slug:'ifrs',en:'IFRS',ar:'المعايير الدولية للتقارير المالية',kw:'ifrs international financial reporting'},
    {slug:'quickbooks',en:'QuickBooks',ar:'كويك بوكس',kw:'quickbooks accounting software'},
    {slug:'sap_finance',en:'SAP Finance',ar:'ساب مالية',kw:'sap fi finance erp'},
    {slug:'tax_accounting',en:'Tax Accounting',ar:'المحاسبة الضريبية',kw:'tax accounting ضريبة'},
    {slug:'payroll',en:'Payroll',ar:'كشوف الرواتب',kw:'payroll رواتب'},
    {slug:'financial_reporting',en:'Financial Reporting',ar:'إعداد التقارير المالية',kw:'financial reporting تقارير مالية'},
    {slug:'budgeting',en:'Budgeting',ar:'إعداد الميزانيات',kw:'budgeting ميزانية'},
    {slug:'cost_accounting',en:'Cost Accounting',ar:'محاسبة التكاليف',kw:'cost accounting تكاليف'},
    {slug:'auditing',en:'Auditing',ar:'التدقيق المحاسبي',kw:'auditing تدقيق مراجعة'},
    {slug:'investment_analysis',en:'Investment Analysis',ar:'تحليل الاستثمار',kw:'investment analysis استثمار'},
    {slug:'risk_management',en:'Risk Management',ar:'إدارة المخاطر',kw:'risk management مخاطر'},
    {slug:'financial_planning',en:'Financial Planning',ar:'التخطيط المالي',kw:'financial planning تخطيط مالي'},
    // ── Human Resources ──
    {slug:'hr',en:'Human Resources',ar:'الموارد البشرية',kw:'hr human resources موارد بشرية'},
    {slug:'talent_acquisition',en:'Talent Acquisition',ar:'استقطاب المواهب',kw:'talent acquisition recruitment استقطاب'},
    {slug:'performance_mgmt',en:'Performance Management',ar:'إدارة الأداء',kw:'performance management أداء'},
    {slug:'training_dev',en:'Training & Development',ar:'التدريب والتطوير',kw:'training development تدريب تطوير'},
    {slug:'employee_relations',en:'Employee Relations',ar:'علاقات الموظفين',kw:'employee relations علاقات'},
    {slug:'compensation',en:'Compensation & Benefits',ar:'التعويضات والمزايا',kw:'compensation benefits مزايا'},
    {slug:'onboarding',en:'Onboarding',ar:'تأهيل الموظفين',kw:'onboarding تأهيل'},
    {slug:'labor_law',en:'Labor Law',ar:'قانون العمل',kw:'labor law قانون عمل'},
    {slug:'hris',en:'HRIS',ar:'نظام معلومات الموارد البشرية',kw:'hris hr system موارد بشرية نظام'},
    {slug:'hr_analytics',en:'HR Analytics',ar:'تحليلات الموارد البشرية',kw:'hr analytics تحليل موارد'},
    // ── Cybersecurity ──
    {slug:'cybersecurity',en:'Cybersecurity',ar:'الأمن السيبراني',kw:'security cyber أمن سيبراني'},
    {slug:'pen_testing',en:'Penetration Testing',ar:'اختبار الاختراق',kw:'pen test penetration اختراق'},
    {slug:'network_security',en:'Network Security',ar:'أمن الشبكات',kw:'network security أمن شبكات'},
    {slug:'ethical_hacking',en:'Ethical Hacking',ar:'القرصنة الأخلاقية',kw:'ethical hacking قرصنة أخلاقية'},
    {slug:'vulnerability_assessment',en:'Vulnerability Assessment',ar:'تقييم الثغرات',kw:'vulnerability assessment ثغرات'},
    {slug:'siem',en:'SIEM',ar:'SIEM',kw:'siem security information event management'},
    {slug:'digital_forensics',en:'Digital Forensics',ar:'الجنائيات الرقمية',kw:'digital forensics جنائيات رقمية'},
    {slug:'soc',en:'SOC',ar:'مركز عمليات الأمن',kw:'soc security operations center'},
    {slug:'malware_analysis',en:'Malware Analysis',ar:'تحليل البرمجيات الخبيثة',kw:'malware analysis فيروسات'},
    {slug:'cryptography',en:'Cryptography',ar:'التشفير',kw:'cryptography encryption تشفير'},
    {slug:'iso27001',en:'ISO 27001',ar:'ISO 27001',kw:'iso 27001 security standard'},
    {slug:'incident_response',en:'Incident Response',ar:'الاستجابة للحوادث',kw:'incident response security'},
    {slug:'osint',en:'OSINT',ar:'استخبارات المصادر المفتوحة',kw:'osint open source intelligence'},
    // ── Networking ──
    {slug:'networking',en:'Networking',ar:'شبكات',kw:'network ccna tcp/ip شبكات'},
    {slug:'ccna',en:'CCNA',ar:'CCNA',kw:'ccna cisco networking'},
    {slug:'cisco',en:'Cisco',ar:'سيسكو',kw:'cisco networking routers switches'},
    {slug:'vpn',en:'VPN',ar:'VPN',kw:'vpn virtual private network'},
    {slug:'lan_wan',en:'LAN / WAN',ar:'LAN / WAN',kw:'lan wan networking'},
    {slug:'mikrotik',en:'MikroTik',ar:'ميكروتيك',kw:'mikrotik router networking'},
    {slug:'network_admin',en:'Network Administration',ar:'إدارة الشبكات',kw:'network administration إدارة شبكات'},
    {slug:'routing_switching',en:'Routing & Switching',ar:'التوجيه والتبديل',kw:'routing switching cisco'},
    {slug:'network_monitoring',en:'Network Monitoring',ar:'مراقبة الشبكات',kw:'network monitoring wireshark'},
    {slug:'wireshark',en:'Wireshark',ar:'وايرشارك',kw:'wireshark packet analysis'},
    {slug:'voip',en:'VoIP',ar:'VoIP',kw:'voip ip telephony'},
    // ── AI / Data ──
    {slug:'machine_learning',en:'Machine Learning',ar:'تعلم الآلة',kw:'ml ai ذكاء اصطناعي'},
    {slug:'deep_learning',en:'Deep Learning',ar:'التعلم العميق',kw:'dl neural network شبكات عصبية'},
    {slug:'data_analysis',en:'Data Analysis',ar:'تحليل البيانات',kw:'data analyst تحليل بيانات'},
    {slug:'data_science',en:'Data Science',ar:'علم البيانات',kw:'datascience علم البيانات'},
    {slug:'tensorflow',en:'TensorFlow',ar:'تنسرفلو',kw:'google ai tensorflow'},
    {slug:'pytorch',en:'PyTorch',ar:'بايتورش',kw:'pytorch deep learning'},
    {slug:'pandas',en:'Pandas',ar:'باندا',kw:'python data pandas'},
    {slug:'numpy',en:'NumPy',ar:'نمباي',kw:'python math numpy'},
    {slug:'powerbi',en:'Power BI',ar:'باور بي آي',kw:'powerbi microsoft bi تحليل'},
    {slug:'tableau',en:'Tableau',ar:'تابلو',kw:'data visualization tableau'},
    {slug:'nlp',en:'NLP',ar:'معالجة اللغة الطبيعية',kw:'natural language processing nlp'},
    {slug:'computer_vision',en:'Computer Vision',ar:'رؤية الحاسوب',kw:'computer vision image recognition'},
    {slug:'generative_ai',en:'Generative AI',ar:'الذكاء الاصطناعي التوليدي',kw:'generative ai llm chatgpt'},
    {slug:'mlops',en:'MLOps',ar:'MLOps',kw:'mlops machine learning operations'},
    {slug:'apache_spark',en:'Apache Spark',ar:'أباتشي سبارك',kw:'spark big data apache'},
    {slug:'hadoop',en:'Hadoop',ar:'هادوب',kw:'hadoop big data mapreduce'},
    {slug:'etl',en:'ETL',ar:'ETL',kw:'etl extract transform load data'},
    {slug:'data_warehousing',en:'Data Warehousing',ar:'مستودعات البيانات',kw:'data warehouse dwh'},
    // ── Human Languages ──
    {slug:'arabic_lang',en:'Arabic Language',ar:'اللغة العربية',kw:'arabic language عربي'},
    {slug:'english_lang',en:'English Language',ar:'اللغة الإنجليزية',kw:'english language إنجليزي'},
    {slug:'french_lang',en:'French Language',ar:'اللغة الفرنسية',kw:'french français فرنسي'},
    {slug:'german_lang',en:'German Language',ar:'اللغة الألمانية',kw:'german deutsch ألماني'},
    {slug:'spanish_lang',en:'Spanish Language',ar:'اللغة الإسبانية',kw:'spanish español إسباني'},
    {slug:'chinese_lang',en:'Chinese Language',ar:'اللغة الصينية',kw:'chinese mandarin صيني'},
    {slug:'turkish_lang',en:'Turkish Language',ar:'اللغة التركية',kw:'turkish türkçe تركي'},
    {slug:'italian_lang',en:'Italian Language',ar:'اللغة الإيطالية',kw:'italian italiano إيطالي'},
    {slug:'korean_lang',en:'Korean Language',ar:'اللغة الكورية',kw:'korean 한국어 كوري'},
    {slug:'japanese_lang',en:'Japanese Language',ar:'اللغة اليابانية',kw:'japanese 日本語 ياباني'},
    {slug:'russian_lang',en:'Russian Language',ar:'اللغة الروسية',kw:'russian روسي'},
    {slug:'portuguese_lang',en:'Portuguese Language',ar:'اللغة البرتغالية',kw:'portuguese برتغالي'},
    {slug:'persian_lang',en:'Persian Language',ar:'اللغة الفارسية',kw:'persian farsi فارسي'},
    {slug:'arabic_typing',en:'Arabic Typing',ar:'طباعة عربية',kw:'arabic typing طباعة عربية'},
    {slug:'translation',en:'Translation',ar:'ترجمة',kw:'translation ترجمة english arabic'},
    {slug:'technical_writing',en:'Technical Writing',ar:'الكتابة التقنية',kw:'technical writing documentation توثيق'},
    // ── Education & Training ──
    {slug:'curriculum_design',en:'Curriculum Design',ar:'تصميم المناهج',kw:'curriculum design مناهج'},
    {slug:'elearning',en:'E-Learning',ar:'التعليم الإلكتروني',kw:'elearning online learning تعلم إلكتروني'},
    {slug:'instructional_design',en:'Instructional Design',ar:'التصميم التعليمي',kw:'instructional design تصميم تعليمي'},
    {slug:'lms',en:'LMS',ar:'نظام إدارة التعلم',kw:'lms learning management system moodle'},
    {slug:'coaching',en:'Coaching',ar:'الكوتشينج',kw:'coaching personal development كوتشينج'},
    {slug:'mentoring',en:'Mentoring',ar:'التوجيه والإرشاد',kw:'mentoring coaching توجيه'},
    {slug:'toefl_ielts',en:'TOEFL / IELTS',ar:'TOEFL / IELTS',kw:'toefl ielts english exam'},
    {slug:'edu_technology',en:'Educational Technology',ar:'تكنولوجيا التعليم',kw:'edtech educational technology'},
    {slug:'classroom_mgmt',en:'Classroom Management',ar:'إدارة الفصل الدراسي',kw:'classroom management فصل دراسي'},
    // ── Engineering ──
    {slug:'solidworks',en:'SolidWorks',ar:'سوليدووركس',kw:'solidworks cad 3d design'},
    {slug:'revit',en:'Revit',ar:'ريفيت',kw:'revit bim architecture'},
    {slug:'catia',en:'CATIA',ar:'كاتيا',kw:'catia cad automotive'},
    {slug:'bim',en:'BIM',ar:'نمذجة معلومات البناء',kw:'bim building information modeling'},
    {slug:'structural_analysis',en:'Structural Analysis',ar:'التحليل الإنشائي',kw:'structural analysis engineering تحليل إنشائي'},
    {slug:'plc',en:'PLC Programming',ar:'برمجة PLC',kw:'plc programming automation'},
    {slug:'scada',en:'SCADA',ar:'SCADA',kw:'scada control systems automation'},
    {slug:'six_sigma',en:'Six Sigma',ar:'ستة سيجما',kw:'six sigma quality lean'},
    {slug:'lean_manufacturing',en:'Lean Manufacturing',ar:'التصنيع الرشيق',kw:'lean manufacturing kaizen'},
    {slug:'quality_control',en:'Quality Control',ar:'ضبط الجودة',kw:'quality control qc جودة'},
    {slug:'hse',en:'HSE / Safety',ar:'الصحة والسلامة والبيئة',kw:'hse health safety environment سلامة'},
    {slug:'sap_pm',en:'SAP PM',ar:'ساب صيانة',kw:'sap pm plant maintenance erp'},
    // ── Medical & Nursing ──
    {slug:'patient_care',en:'Patient Care',ar:'رعاية المرضى',kw:'patient care رعاية مرضى'},
    {slug:'clinical_skills',en:'Clinical Skills',ar:'المهارات السريرية',kw:'clinical skills سريري'},
    {slug:'emr',en:'EMR / EHR',ar:'السجلات الطبية الإلكترونية',kw:'emr ehr electronic medical records'},
    {slug:'medical_coding',en:'Medical Coding',ar:'الترميز الطبي',kw:'medical coding icd billing'},
    {slug:'cpr',en:'CPR / First Aid',ar:'الإسعافات الأولية',kw:'cpr first aid إسعافات'},
    {slug:'phlebotomy',en:'Phlebotomy',ar:'سحب الدم',kw:'phlebotomy blood draw'},
    {slug:'medical_lab',en:'Medical Laboratory',ar:'المختبر الطبي',kw:'medical laboratory مختبر'},
    {slug:'radiology',en:'Radiology',ar:'الأشعة',kw:'radiology imaging أشعة'},
    {slug:'pharmacy_skills',en:'Pharmacy',ar:'الصيدلة',kw:'pharmacy dispensing صيدلة'},
    {slug:'healthcare_admin',en:'Healthcare Administration',ar:'إدارة الرعاية الصحية',kw:'healthcare administration رعاية صحية'},
    {slug:'infection_control',en:'Infection Control',ar:'مكافحة العدوى',kw:'infection control prevention عدوى'},
    // ── Crafts & Technical Trades ──
    {slug:'electrical_installation',en:'Electrical Installation',ar:'التركيبات الكهربائية',kw:'electrical installation كهرباء تركيب'},
    {slug:'plumbing_craft',en:'Plumbing',ar:'السباكة',kw:'plumbing سباكة'},
    {slug:'carpentry',en:'Carpentry',ar:'النجارة',kw:'carpentry woodwork نجارة'},
    {slug:'hvac',en:'HVAC / Air Conditioning',ar:'تكييف الهواء',kw:'hvac ac air conditioning تكييف'},
    {slug:'welding',en:'Welding',ar:'اللحام',kw:'welding لحام'},
    {slug:'auto_mechanics',en:'Auto Mechanics',ar:'ميكانيكا السيارات',kw:'auto mechanics ميكانيكا سيارات'},
    {slug:'painting_craft',en:'Painting & Finishing',ar:'الدهان',kw:'painting دهان'},
    {slug:'tiling',en:'Tiling',ar:'التبليط والسيراميك',kw:'tiling بلاط سيراميك'},
    {slug:'cctv',en:'CCTV Installation',ar:'تركيب كاميرات المراقبة',kw:'cctv surveillance cameras مراقبة'},
    {slug:'alarm_systems',en:'Alarm Systems',ar:'أنظمة الإنذار',kw:'alarm systems إنذار حماية'},
    {slug:'fiber_optic',en:'Fiber Optic',ar:'الألياف البصرية',kw:'fiber optic networking ألياف بصرية'},
    // ── Restaurants & Hotels ──
    {slug:'food_service',en:'Food Service',ar:'خدمة الطعام',kw:'food service طعام خدمة'},
    {slug:'hotel_management',en:'Hotel Management',ar:'إدارة الفندق',kw:'hotel management فندق'},
    {slug:'hospitality',en:'Hospitality',ar:'الضيافة',kw:'hospitality ضيافة'},
    {slug:'kitchen_management',en:'Kitchen Management',ar:'إدارة المطبخ',kw:'kitchen chef cooking مطبخ'},
    {slug:'food_safety',en:'Food Safety / HACCP',ar:'سلامة الغذاء',kw:'food safety haccp سلامة غذاء'},
    {slug:'pos_systems',en:'POS Systems',ar:'أنظمة نقاط البيع',kw:'pos point of sale نقطة بيع'},
    {slug:'event_management',en:'Event Management',ar:'إدارة الفعاليات',kw:'event management فعاليات'},
    {slug:'bartending',en:'Bartending',ar:'بارتندر',kw:'bartending drinks bar'},
    {slug:'catering',en:'Catering',ar:'خدمات الضيافة والتموين',kw:'catering تموين ضيافة'},
    // ── Logistics & Supply Chain ──
    {slug:'supply_chain',en:'Supply Chain Management',ar:'إدارة سلسلة التوريد',kw:'supply chain سلسلة توريد'},
    {slug:'inventory_management',en:'Inventory Management',ar:'إدارة المخزون',kw:'inventory management مخزون'},
    {slug:'warehouse_management',en:'Warehouse Management',ar:'إدارة المستودعات',kw:'warehouse management مستودعات'},
    {slug:'shipping',en:'Shipping & Freight',ar:'الشحن والنقل',kw:'shipping freight شحن'},
    {slug:'customs',en:'Customs & Clearance',ar:'الجمارك والتخليص',kw:'customs clearance جمارك'},
    {slug:'fleet_management',en:'Fleet Management',ar:'إدارة الأسطول',kw:'fleet management أسطول'},
    {slug:'demand_planning',en:'Demand Planning',ar:'تخطيط الطلب',kw:'demand planning forecasting'},
    {slug:'erp',en:'ERP Systems',ar:'أنظمة ERP',kw:'erp enterprise resource planning'},
    {slug:'sap_mm',en:'SAP MM',ar:'ساب مشتريات',kw:'sap mm materials management erp'},
    // ── Customer Service ──
    {slug:'customer_service',en:'Customer Service',ar:'خدمة العملاء',kw:'customer service support خدمة عملاء'},
    {slug:'technical_support',en:'Technical Support',ar:'الدعم الفني',kw:'technical support دعم فني'},
    {slug:'help_desk',en:'Help Desk',ar:'مكتب المساعدة',kw:'help desk support helpdesk'},
    {slug:'call_center',en:'Call Center',ar:'مركز الاتصال',kw:'call center مركز اتصال'},
    {slug:'complaint_handling',en:'Complaint Handling',ar:'معالجة الشكاوى',kw:'complaint handling شكاوى'},
    {slug:'zendesk',en:'Zendesk',ar:'زن ديسك',kw:'zendesk support crm'},
    {slug:'after_sales',en:'After-Sales Service',ar:'خدمة ما بعد البيع',kw:'after sales service ما بعد البيع'},
    // ── Soft Skills (Extended) ──
    {slug:'emotional_intelligence',en:'Emotional Intelligence',ar:'الذكاء العاطفي',kw:'emotional intelligence ذكاء عاطفي eq'},
    {slug:'adaptability',en:'Adaptability',ar:'القدرة على التكيف',kw:'adaptability flexibility تكيف'},
    {slug:'creativity',en:'Creativity',ar:'الإبداع',kw:'creativity innovation إبداع ابتكار'},
    {slug:'teamwork',en:'Teamwork',ar:'العمل الجماعي',kw:'teamwork collaboration عمل فريق'},
    {slug:'presentation_skills',en:'Presentation Skills',ar:'مهارات العرض والتقديم',kw:'presentation skills عرض تقديم'},
    {slug:'writing_skills',en:'Writing Skills',ar:'مهارات الكتابة',kw:'writing skills كتابة'},
    {slug:'active_listening',en:'Active Listening',ar:'الاستماع الفعال',kw:'active listening استماع'},
    {slug:'conflict_resolution',en:'Conflict Resolution',ar:'حل النزاعات',kw:'conflict resolution نزاع'},
    {slug:'decision_making',en:'Decision Making',ar:'صنع القرار',kw:'decision making قرار'},
    {slug:'research_skills',en:'Research Skills',ar:'مهارات البحث',kw:'research skills بحث'},
  ];

  // Level color map
  var LEVEL_COLORS = {
    'مبتدئ': {color:'#9ca3af', bg:'rgba(156,163,175,.15)'},
    'متوسط': {color:'#60a5fa', bg:'rgba(96,165,250,.15)'},
    'جيد':   {color:'#a78bfa', bg:'rgba(167,139,250,.15)'},
    'متقدم': {color:'#00c896', bg:'rgba(0,200,150,.15)'},
    'محترف': {color:'#fbbf24', bg:'rgba(251,191,36,.15)'},
  };

  // Words indicating merged skill+level (caught in validation)
  var LEVEL_WORDS = ['مبتدئ','متوسط','جيد','متقدم','محترف','متخصص','خبير',
                     'beginner','intermediate','advanced','expert','junior','senior','mid-level'];

  // ── Catalog search (returns up to 8 matches) ──
  function _search(q){
    if(!q || q.length < 1) return [];
    var ql = q.toLowerCase();
    var results = [];
    for(var i=0; i<CATALOG.length; i++){
      var s = CATALOG[i];
      if(s.en.toLowerCase().indexOf(ql) !== -1
      || s.ar.indexOf(q) !== -1
      || s.slug.indexOf(ql) !== -1
      || s.kw.toLowerCase().indexOf(ql) !== -1){
        results.push(s);
        if(results.length >= 8) break;
      }
    }
    return results;
  }

  // ── Normalize: map input to canonical en name if it matches catalog ──
  function _normalize(raw){
    var cleaned = raw.trim();
    var ql = cleaned.toLowerCase();
    for(var i=0; i<CATALOG.length; i++){
      var s = CATALOG[i];
      if(s.slug === ql || s.en.toLowerCase() === ql || s.ar === cleaned){
        return s.en;
      }
      var kws = s.kw.split(' ');
      for(var j=0; j<kws.length; j++){
        if(kws[j] && kws[j].toLowerCase() === ql) return s.en;
      }
    }
    return cleaned;
  }

  // ── _isOfficial: true if normalized skill name matches catalog ──
  function _isOfficial(name){
    var nl = (name || '').toLowerCase().trim();
    for(var i=0; i<CATALOG.length; i++){
      if(CATALOG[i].en.toLowerCase() === nl || CATALOG[i].slug === nl) return true;
    }
    return false;
  }

  // ── Validation — returns error string or null ──
  function _validate(skill){
    if(!skill) return 'اسم المهارة مطلوب';
    if(skill.length < 2) return 'اسم المهارة قصير جداً (حرفان على الأقل)';
    // Professional content check (emoji + profanity)
    var _pcErr = window._scCheckProfessional && window._scCheckProfessional(skill);
    if(_pcErr) return _pcErr;
    if(!/[a-zA-Z؀-ۿ]/.test(skill)) return 'اسم المهارة غير صالح — يجب أن يحتوي على حروف';
    // Detect merged "skill + level" pattern
    var sl = skill.toLowerCase();
    for(var i=0; i<LEVEL_WORDS.length; i++){
      if(sl.indexOf(LEVEL_WORDS[i]) !== -1){
        return 'اكتب اسم المهارة فقط — واختر المستوى من القائمة أدناه';
      }
    }
    return null;
  }

  // ── Case-insensitive duplicate check against current profile ──
  function _isDuplicate(skill){
    var sl = skill.toLowerCase();
    var existing = (window._scProfile && window._scProfile.skills) || [];
    for(var i=0; i<existing.length; i++){
      if((existing[i].skill || '').toLowerCase() === sl) return true;
    }
    return false;
  }

  // ── Autocomplete ──
  var _dropResults = [];
  var _activeIdx   = -1;

  function _getDrop(){ return f('skillDrop'); }

  function _showDrop(results){
    var drop = _getDrop();
    if(!drop) return;
    _dropResults = results;
    _activeIdx   = -1;
    if(!results.length){ _hideDrop(); return; }

    var html = '';
    for(var i=0; i<results.length; i++){
      var s = results[i];
      html += '<div class="sk-ac-item" data-idx="'+i+'">'
        + '<span class="sk-ac-en">'+esc(s.en)+'</span>'
        + (s.ar !== s.en ? '<span class="sk-ac-ar">'+esc(s.ar)+'</span>' : '')
        + '</div>';
    }
    drop.innerHTML = html;
    drop.style.display = 'block';

    var items = drop.querySelectorAll('.sk-ac-item');
    for(var j=0; j<items.length; j++){
      (function(item, res){
        item.onclick = function(){ _pickResult(res.en); };
      })(items[j], results[j]);
    }
  }

  function _hideDrop(){
    var drop = _getDrop();
    if(drop){ drop.style.display='none'; drop.innerHTML=''; }
    _dropResults = [];
    _activeIdx   = -1;
  }

  function _pickResult(name){
    var inp = f('skillName');
    if(inp) inp.value = name;
    _hideDrop();
    if(inp) inp.focus();
  }

  function _moveActive(dir){
    var drop = _getDrop();
    if(!drop || drop.style.display==='none' || !_dropResults.length) return;
    var items = drop.querySelectorAll('.sk-ac-item');
    if(!items.length) return;
    if(_activeIdx >= 0) items[_activeIdx].classList.remove('sk-ac-active');
    _activeIdx = (_activeIdx + dir + _dropResults.length) % _dropResults.length;
    items[_activeIdx].classList.add('sk-ac-active');
    items[_activeIdx].scrollIntoView({block:'nearest'});
  }

  function _selectActive(){
    if(_activeIdx < 0 || !_dropResults[_activeIdx]) return false;
    _pickResult(_dropResults[_activeIdx].en);
    return true;
  }

  function _initAC(){
    var inp = f('skillName');
    if(!inp) return;

    inp.addEventListener('input', function(){
      _showDrop(_search(inp.value));
    });

    inp.addEventListener('keydown', function(e){
      var drop = _getDrop();
      var open = drop && drop.style.display !== 'none';
      if(e.key === 'ArrowDown')  { e.preventDefault(); if(open) _moveActive(1);       }
      else if(e.key === 'ArrowUp')  { e.preventDefault(); if(open) _moveActive(-1);      }
      else if(e.key === 'Enter')    { if(open && _selectActive()) e.preventDefault();     }
      else if(e.key === 'Escape')   { _hideDrop();                                        }
    });

    inp.addEventListener('blur', function(){
      setTimeout(_hideDrop, 160);
    });
  }

  // ── Modal ──
  function openModal(){
    sv('skillName','');
    sv('skillLevel','');
    _hideDrop();
    overlay.classList.add('open');
    if(window._scPushHistory) window._scPushHistory('skill');
    setTimeout(function(){ var inp=f('skillName'); if(inp) inp.focus(); }, 120);
  }
  function closeModal(){
    _hideDrop();
    overlay.classList.remove('open');
    if(window._scHistoryReset) window._scHistoryReset();
  }

  if(closeBtn)  closeBtn.onclick  = closeModal;
  if(cancelBtn) cancelBtn.onclick = closeModal;
  overlay.addEventListener('click', function(e){ if(e.target===overlay) closeModal(); });

  _initAC();

  // ── Save ──
  saveBtn.onclick = function(){
    var raw   = fv('skillName');
    var skill = _normalize(raw);
    var level = fv('skillLevel') || null;

    var err = _validate(skill);
    if(err){ toast(err); return; }

    if(_isDuplicate(skill)){
      toast('هذه المهارة موجودة مسبقاً في ملفك الشخصي');
      return;
    }

    saveBtn.disabled    = true;
    saveBtn.textContent = 'جاري الحفظ…';

    addSkill(_scUserId, {skill:skill, level:level}).then(function(res){
      if(!res.ok){
        var _det = res.data && res.data.detail;
        var _msg = (_det && typeof _det==='object' && _det.message) ? _det.message
                 : (typeof _det==='string' ? _det : 'حدث خطأ');
        toast(_msg);
        return;
      }
      var entry = res.data.skill;
      var cache = window._scProfile;
      if(cache){
        var found = false;
        var skills = cache.skills || [];
        for(var i=0; i<skills.length; i++){
          if((skills[i].skill||'').toLowerCase() === (entry.skill||'').toLowerCase()){
            skills[i] = entry; found = true; break;
          }
        }
        if(!found) cache.skills = [entry].concat(skills);
        else cache.skills = skills;
      }
      closeModal();
      toast('تمت إضافة المهارة');
      _reRenderSkills();
      if(window._bgRefetch) window._bgRefetch();
    }).catch(function(){
      toast('خطأ في الاتصال بالخادم');
    }).finally(function(){
      saveBtn.disabled    = false;
      saveBtn.textContent = 'حفظ';
    });
  };

  // ── Build Skills HTML ──
  window._buildSkillsHTML = function(skills, isOwner){
    var addBtn = isOwner
      ? '<button class="sc-section-add owner-only" onclick="window._skillOpenAdd()">'
        + '<svg class="ico-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
        + '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>'
        + ' إضافة مهارة</button>'
      : '';
    if(!skills || !skills.length)
      return addBtn + '<div class="sc-empty">لا توجد مهارات بعد</div>';

    var chips = '<div class="sc-skills-wrap">';
    for(var i=0; i<skills.length; i++){
      var s      = skills[i];
      var name   = esc(s.skill || '');
      var level  = s.level ? esc(s.level) : '';
      var lv     = LEVEL_COLORS[s.level] || {color:'#9ca3af', bg:'rgba(156,163,175,.15)'};
      var badge  = level
        ? '<span class="sc-skill-badge" style="color:'+lv.color+';background:'+lv.bg+'">'+level+'</span>'
        : '';
      // Custom skill badge — shown for skills not in the official catalog
      var isOff  = _isOfficial(s.skill || '');
      var cstBadge = !isOff
        ? '<span class="sc-skill-badge sc-skill-custom-badge">مخصصة</span>'
        : '';
      var del = isOwner
        ? '<button class="sc-skill-del owner-only" data-skill-id="'+s.id+'"'
          + ' onclick="window._skillConfirmDelete(this.dataset.skillId)"'
          + ' title="حذف" aria-label="حذف المهارة">×</button>'
        : '';
      var chipClass = 'sc-skill-chip' + (!isOff ? ' sc-skill-chip-custom' : '');
      chips += '<span class="'+chipClass+'">'
        + '<span class="sc-skill-name">'+name+'</span>'
        + badge
        + cstBadge
        + del
        + '</span>';
    }
    chips += '</div>';
    return addBtn + chips;
  };

  function _reRenderSkills(){
    var el = document.getElementById('scSkillsPane');
    if(!el) return;
    var cache   = window._scProfile;
    var skills  = cache ? (cache.skills || []) : [];
    var isOwner = (window._scViewerType === 'owner');
    el.innerHTML = window._buildSkillsHTML(skills, isOwner);
    if(window.lucide && lucide.createIcons) lucide.createIcons();
  }
  window._reRenderSkills = _reRenderSkills;

  window._skillOpenAdd = function(){ openModal(); };

  window._skillConfirmDelete = function(id){
    id = parseInt(id, 10);
    scConfirm('هل أنت متأكد من حذف هذه المهارة؟', function(){
      deleteSkill(id).then(function(res){
        if(!res.ok){ toast('حدث خطأ أثناء الحذف'); return; }
        var cache = window._scProfile;
        if(cache) cache.skills = (cache.skills||[]).filter(function(s){ return s.id!==id; });
        _reRenderSkills();
        toast('تم حذف المهارة');
        if(window._bgRefetch) window._bgRefetch();
      }).catch(function(){ toast('خطأ في الاتصال بالخادم'); });
    });
  };

})();
