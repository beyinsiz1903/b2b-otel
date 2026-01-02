{
  "meta": {
    "app_name": "CapX Sapanca-Kartepe",
    "description": "B2B hotel-to-hotel capacity exchange platform with anonymous listings and structured request/match workflow.",
    "audience": "Hotel revenue managers, sales, and operations teams in Sapanca & Kartepe region",
    "brand_attributes": ["professional", "trustworthy", "discreet", "efficient", "transactional clarity"]
  },
  "design_personality": {
    "style_mix": "Swiss/International Typographic Style meets Minimalist B2B. Card-layout + Split-screen modals. Light use of Glassmorphism in secondary panels only.",
    "layout_pattern": "Z-pattern for dashboard, grid/card for listings, split-pane for match detail",
    "motion_tone": "calm, purposeful, 150–250ms transitions, no bounce"
  },
  "color_system": {
    "core_palette": {
      "lake-slate": "#3A556A",
      "pine": "#2E6B57",
      "mist": "#EEF2F4",
      "stone": "#1F2933",
      "sand": "#DCC9A6",
      "steel": "#6B7C93"
    },
    "ui_neutrals": {
      "bg": "#F7F8FA",
      "surface": "#FFFFFF",
      "border": "#E6E8EC",
      "muted": "#8C99A5",
      "focus": "#0F766E"
    },
    "semantic_states": {
      "available": {"bg": "#E7F6EE", "fg": "#176B45", "border": "#BDE3CF"},
      "limited": {"bg": "#FFF7E6", "fg": "#8A5A00", "border": "#FFE2B3"},
      "alternative": {"bg": "#E6F1FF", "fg": "#16457A", "border": "#C9E0FF"},
      "locked": {"bg": "#F2F4F7", "fg": "#5E6A74", "border": "#E5E7EB"},
      "accepted": {"bg": "#E9F7FB", "fg": "#0B6B82", "border": "#BFE9F4"},
      "rejected": {"bg": "#FCEAEA", "fg": "#8A1F1F", "border": "#F6C4C4"}
    },
    "charts": {
      "primary": "#2E6B57",
      "secondary": "#3A556A",
      "accent": "#DCC9A6",
      "muted": "#C8D5E1"
    },
    "gradient_usage": {
      "allowed": "Section backgrounds (hero header only) with subtle 2–3 color diagonal gradient using mist->sand->transparent overlay. Keep under 20% viewport.",
      "example_css": "bg-[linear-gradient(135deg,rgba(238,242,244,0.8)_0%,rgba(220,201,166,0.35)_60%,rgba(238,242,244,0)_100%)]",
      "not_allowed": ["no dark/saturated purple/pink gradients", "no gradients on small UI elements", "never in dense tables"]
    }
  },
  "css_tokens": {
    "how_to_apply": "Extend /src/index.css :root variables with semantic tokens below; keep dark theme equivalent values.",
    "root_vars_snippet": ":root{--brand-lake-slate:58 27% 33%;--brand-pine:158 40% 30%;--brand-mist:210 22% 95%;--brand-stone:210 20% 16%;--brand-sand:41 40% 76%;--brand-steel:213 18% 50%;--state-available:149 62% 26%;--state-available-bg:149 45% 92%;--state-limited:35 100% 27%;--state-limited-bg:38 100% 95%;--state-alternative:214 67% 27%;--state-alternative-bg:214 100% 94%;--state-locked:210 12% 40%;--state-locked-bg:210 15% 96%;--state-accepted:191 83% 26%;--state-accepted-bg:191 78% 94%;--state-rejected:0 64% 32%;--state-rejected-bg:0 82% 96%;--elev-1:0 0% 100%;--elev-2:210 20% 98%;--ring:174 72% 28%} .dark{--brand-lake-slate:210 18% 82%;--brand-pine:158 24% 68%;--brand-mist:210 6% 10%;--brand-stone:210 6% 92%;--brand-sand:41 28% 60%;--brand-steel:213 14% 72%;--state-available-bg:149 25% 16%;--state-limited-bg:38 25% 16%;--state-alternative-bg:214 20% 16%;--state-locked-bg:210 8% 20%;--state-accepted-bg:191 24% 16%;--state-rejected-bg:0 24% 16%}",
    "tailwind_mapping": [
      "bg-background -> hsl(var(--brand-mist))",
      "text-foreground -> hsl(var(--brand-stone))",
      "ring -> hsl(var(--ring))"
    ]
  },
  "typography": {
    "fonts": {
      "heading": "Chivo",
      "body": "Karla",
      "mono": "IBM Plex Mono"
    },
    "import": {
      "google_links": [
        "https://fonts.googleapis.com/css2?family=Chivo:wght@400;500;600;700&display=swap",
        "https://fonts.googleapis.com/css2?family=Karla:wght@400;500;600;700&display=swap",
        "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap"
      ],
      "setup": "Add links in public/index.html head. Then set via Tailwind theme.extend.fontFamily or utility classes."
    },
    "scale": {
      "h1": "text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight",
      "h2": "text-base md:text-lg font-medium text-[color:var(--foreground)]",
      "body": "text-base md:text-base text-[color:var(--foreground)]",
      "small": "text-sm text-muted-foreground"
    }
  },
  "buttons": {
    "tone": "Professional / Corporate",
    "tokens": {
      "--btn-radius": "0.5rem",
      "--btn-shadow": "0 1px 2px rgba(0,0,0,0.06)",
      "--btn-motion": "200ms"
    },
    "variants": {
      "primary": "bg-[hsl(var(--brand-pine))] text-white hover:bg-emerald-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))]",
      "secondary": "bg-white text-[hsl(var(--brand-lake-slate))] border border-[hsl(var(--border))] hover:bg-[hsl(var(--brand-mist))]",
      "ghost": "bg-transparent text-[hsl(var(--brand-lake-slate))] hover:bg-[hsl(var(--brand-mist))]"
    },
    "sizes": {
      "sm": "h-9 px-3",
      "md": "h-10 px-4",
      "lg": "h-12 px-5"
    },
    "micro_interactions": "Use transition-colors, transition-opacity, duration-200. No transition: all. Press: active:scale-[0.99] with transform-gpu"
  },
  "components": {
    "paths": {
      "badge": "/app/frontend/src/components/ui/badge.jsx",
      "button": "/app/frontend/src/components/ui/button.jsx",
      "card": "/app/frontend/src/components/ui/card.jsx",
      "dialog": "/app/frontend/src/components/ui/dialog.jsx",
      "dropdown_menu": "/app/frontend/src/components/ui/dropdown-menu.jsx",
      "select": "/app/frontend/src/components/ui/select.jsx",
      "input": "/app/frontend/src/components/ui/input.jsx",
      "calendar": "/app/frontend/src/components/ui/calendar.jsx",
      "tabs": "/app/frontend/src/components/ui/tabs.jsx",
      "table": "/app/frontend/src/components/ui/table.jsx",
      "popover": "/app/frontend/src/components/ui/popover.jsx",
      "sheet": "/app/frontend/src/components/ui/sheet.jsx",
      "separator": "/app/frontend/src/components/ui/separator.jsx",
      "toast": "/app/frontend/src/components/ui/sonner.jsx"
    },
    "usage_map": {
      "status_chip": "badge.jsx",
      "filters": ["select.jsx", "calendar.jsx", "popover.jsx"],
      "request_modal": "dialog.jsx",
      "alternative_offer_modal": "dialog.jsx",
      "navigation": ["sheet.jsx", "dropdown-menu.jsx", "tabs.jsx"],
      "data_table": "table.jsx",
      "forms": ["input.jsx", "select.jsx"]
    }
  },
  "icons": {
    "library": "lucide-react (already in project)",
    "usage": "Use size 18–20 for dense tables, 22–24 elsewhere."
  },
  "layout_and_pages": {
    "shell": {
      "header": "Top bar with app name, region switch (Sapanca/Kartepe), quick filters, user menu",
      "sidebar": "Compact icons + labels on md+, sheet on mobile",
      "content": "Max-w-[1280px] mx-auto px-4 md:px-6 lg:px-8 py-4 md:py-6 spacing 2–3x generous"
    },
    "routes": [
      "/auth/login",
      "/auth/register",
      "/dashboard",
      "/listings",
      "/availability",
      "/requests",
      "/match/:id"
    ],
    "auth": {
      "layout": "Split-screen on md+ (left: subdued lake image with noise; right: form card). Single-column on mobile.",
      "components": ["card", "input", "button"],
      "copy_tone": "B2B: 'Sign in to capacity exchange' (no consumer wording)"
    },
    "dashboard": {
      "top_kpis": ["Open capacity", "Active requests", "Matches this month"],
      "widgets": ["Requests timeline (Recharts)", "Status breakdown chips"],
      "micro": "Header background may use subtle gradient+noise <20% viewport; Parallax translate-y on scroll for header image only"
    },
    "listings_feed": {
      "card_fields": ["Region/Micro-location", "Concept (resort, thermal, boutique)", "Capacity", "Date range", "Night count", "Price range", "Availability status chip"],
      "actions": ["Send request", "Quick view"],
      "filters": ["region", "concept", "date-range", "capacity range", "status"],
      "states": ["anonymous", "requested/locked", "matched", "rejected"],
      "tone": "No names until accepted"
    },
    "availability_management": {
      "features": ["Create availability", "Edit", "List"],
      "fields": ["region", "concept", "date-range (shadcn calendar)", "night count", "capacity", "price range", "notes"],
      "ui": "Form in sheet/dialog. Table list with inline edit where appropriate"
    },
    "requests": {
      "tabs": ["Incoming", "Outgoing"],
      "columns": ["Listing summary (anonymous)", "Requested volume", "Proposed terms", "State chip", "Last update", "Actions"],
      "row_actions": ["Accept", "Reject", "Offer alternative", "Open match detail"]
    },
    "match_detail": {
      "structure": "Left: timeline + state; Right: details. After ACCEPT: reveal identities with contact and match reference code.",
      "sections": ["Pre-match (anonymous)", "Decision", "Post-match reveal", "Audit log"],
      "security": "Mask identities until acceptance"
    }
  },
  "grids_spacing": {
    "container": "w-full max-w-[1280px] mx-auto px-4 md:px-6 lg:px-8",
    "cards": "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6",
    "tables": "Use dense variant: text-sm md:text-[15px]; row h-12; md:h-14; 16px cell padding",
    "sections": "space-y-6 md:space-y-10 lg:space-y-12"
  },
  "status_chips": {
    "class_map": {
      "available": "bg-[hsl(var(--state-available-bg))] text-[hsl(var(--state-available))] border border-[hsl(var(--state-available))]/20",
      "limited": "bg-[hsl(var(--state-limited-bg))] text-[hsl(var(--state-limited))] border border-[hsl(var(--state-limited))]/20",
      "alternative": "bg-[hsl(var(--state-alternative-bg))] text-[hsl(var(--state-alternative))] border border-[hsl(var(--state-alternative))]/20",
      "locked": "bg-[hsl(var(--state-locked-bg))] text-[hsl(var(--state-locked))] border border-[hsl(var(--state-locked))]/20",
      "accepted": "bg-[hsl(var(--state-accepted-bg))] text-[hsl(var(--state-accepted))] border border-[hsl(var(--state-accepted))]/20",
      "rejected": "bg-[hsl(var(--state-rejected-bg))] text-[hsl(var(--state-rejected))] border border-[hsl(var(--state-rejected))]/20"
    },
    "size": "h-6 px-2.5 rounded-md text-xs font-medium"
  },
  "interaction_patterns": {
    "modals": "Use dialog.jsx for send-request and offer-alternative. Close on backdrop click disabled when submitting.",
    "filters": "Popover + Select + Calendar for region/concept/date. On mobile, collapse into Sheet.",
    "locking": "After a request is sent, immediately lock the listing (state 'locked') and disable further requests; show tooltip explaining lock.",
    "post_accept_reveal": "On Accept, replace anonymous badges with revealed identity cards + match reference code."
  },
  "micro_interactions": {
    "hover_focus": [
      "Buttons: transition-colors duration-200",
      "Cards: shadow-sm hover:shadow-md duration-200",
      "Chips: subtle scale-100 -> 105 on hover-disabled for informative chips only"
    ],
    "list_entries": "Staggered entrance using Framer Motion on listings feed (12–24ms per item)",
    "scroll": "Parallax translate-y-1 for dashboard header image only"
  },
  "accessibility": {
    "contrast": "All text WCAG AA on both light/dark. Chips use >= 4.5:1 where text on colored bg.",
    "focus": "Use ring offset 2, ring color --ring; ensure keyboard traps avoided in Dialog/Sheet",
    "aria": "Aria labels on icons; tables include scope=col on headers",
    "localization": "Avoid consumer language. Terms: 'capacity', 'request', 'match', 'counterparty hotel'"
  },
  "testing": {
    "data_testid_rule": "All interactive and key info elements MUST include data-testid in kebab-case describing role.",
    "examples": [
      "data-testid=\"listings-filter-region-select\"",
      "data-testid=\"send-request-button\"",
      "data-testid=\"status-chip-locked\"",
      "data-testid=\"match-detail-reference-code\"",
      "data-testid=\"availability-create-submit-button\"",
      "data-testid=\"requests-incoming-tab\""
    ]
  },
  "libraries": {
    "recharts": {
      "install": "npm i recharts",
      "usage": "Small KPI charts on dashboard (donut, bar)."
    },
    "framer_motion": {
      "install": "npm i framer-motion",
      "usage": "Entrance animations for cards/lists; prevent motion for prefers-reduced-motion."
    },
    "clsx_optional": {
      "install": "npm i clsx",
      "usage": "Compose classnames for status chips and states"
    }
  },
  "scaffolds_js": {
    "StatusBadge.js": "export const StatusBadge = ({status, children, ...props}) => { const map = {available: 'bg-[hsl(var(--state-available-bg))] text-[hsl(var(--state-available))] border border-[hsl(var(--state-available))]/20', limited: 'bg-[hsl(var(--state-limited-bg))] text-[hsl(var(--state-limited))] border border-[hsl(var(--state-limited))]/20', alternative:'bg-[hsl(var(--state-alternative-bg))] text-[hsl(var(--state-alternative))] border border-[hsl(var(--state-alternative))]/20', locked:'bg-[hsl(var(--state-locked-bg))] text-[hsl(var(--state-locked))] border border-[hsl(var(--state-locked))]/20', accepted:'bg-[hsl(var(--state-accepted-bg))] text-[hsl(var(--state-accepted))] border border-[hsl(var(--state-accepted))]/20', rejected:'bg-[hsl(var(--state-rejected-bg))] text-[hsl(var(--state-rejected))] border border-[hsl(var(--state-rejected))]/20'}; return <span data-testid={`status-chip-${status}`} className={`inline-flex items-center h-6 px-2.5 rounded-md text-xs font-medium ${map[status]||''}`} {...props}>{children||status}</span> };",
    "SendRequestModal.js": "import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './components/ui/dialog'; import { Button } from './components/ui/button'; import { Input } from './components/ui/input'; import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from './components/ui/select'; import { useState } from 'react'; export const SendRequestModal = ({open,onOpenChange,onSubmit, listingSummary}) => { const [payload,setPayload]=useState({volume:'',nights:'',price:'',note:''}); return (<Dialog open={open} onOpenChange={onOpenChange}><DialogContent aria-describedby=\"\" data-testid=\"send-request-modal\"><DialogHeader><DialogTitle>Send request to counterparty</DialogTitle></DialogHeader><div className=\"grid grid-cols-1 gap-4\"><Input data-testid=\"request-volume-input\" placeholder=\"Volume (rooms)\" value={payload.volume} onChange={e=>setPayload({...payload,volume:e.target.value})}/><Input data-testid=\"request-nights-input\" placeholder=\"Night count\" value={payload.nights} onChange={e=>setPayload({...payload,nights:e.target.value})}/><Input data-testid=\"request-price-input\" placeholder=\"Target price range\" value={payload.price} onChange={e=>setPayload({...payload,price:e.target.value})}/><Input data-testid=\"request-note-input\" placeholder=\"Note (optional)\" value={payload.note} onChange={e=>setPayload({...payload,note:e.target.value})}/></div><DialogFooter><Button data-testid=\"request-cancel-button\" variant=\"ghost\" onClick={()=>onOpenChange(false)}>Cancel</Button><Button data-testid=\"request-submit-button\" onClick={()=>onSubmit(payload)}>Send Request</Button></DialogFooter></DialogContent></Dialog>); }",
    "FiltersBar.js": "import { Popover, PopoverContent, PopoverTrigger } from './components/ui/popover'; import { Button } from './components/ui/button'; import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from './components/ui/select'; import { Calendar } from './components/ui/calendar'; import { useState } from 'react'; export default function FiltersBar(){ const [region,setRegion]=useState('all'); const [concept,setConcept]=useState('all'); const [dateRange,setDateRange]=useState({from:undefined,to:undefined}); return (<div className=\"flex flex-wrap items-center gap-2\"><Select value={region} onValueChange={setRegion}><SelectTrigger data-testid=\"listings-filter-region-select\" className=\"w-[160px]\"><SelectValue placeholder=\"Region\"/></SelectTrigger><SelectContent><SelectItem value=\"all\">All regions</SelectItem><SelectItem value=\"sapanca\">Sapanca</SelectItem><SelectItem value=\"kartepe\">Kartepe</SelectItem></SelectContent></Select><Select value={concept} onValueChange={setConcept}><SelectTrigger data-testid=\"listings-filter-concept-select\" className=\"w-[180px]\"><SelectValue placeholder=\"Concept\"/></SelectTrigger><SelectContent><SelectItem value=\"all\">All concepts</SelectItem><SelectItem value=\"resort\">Resort</SelectItem><SelectItem value=\"thermal\">Thermal</SelectItem><SelectItem value=\"boutique\">Boutique</SelectItem></SelectContent></Select><Popover><PopoverTrigger asChild><Button data-testid=\"listings-filter-date-button\" variant=\"secondary\">Date range</Button></PopoverTrigger><PopoverContent align=\"start\"><Calendar mode=\"range\" selected={dateRange} onSelect={setDateRange} numberOfMonths={2} /></PopoverContent></Popover></div>); }
"
  },
  "image_urls": [
    {"url": "https://images.unsplash.com/photo-1767170549468-2304b1b46e9b?crop=entropy&cs=srgb&fm=jpg&q=85", "description": "A lone boat on a calm, misty lake", "category": "hero-background (dashboard header)"},
    {"url": "https://images.unsplash.com/photo-1767170549500-f37591ac15f9?crop=entropy&cs=srgb&fm=jpg&q=85", "description": "Seagull over calm water near red buoy", "category": "empty-state / illustration background"},
    {"url": "https://images.pexels.com/photos/5712965/pexels-photo-5712965.jpeg", "description": "Coastal reeds in mist (neutral nature texture)", "category": "secondary section background strip"}
  ],
  "component_path": {
    "from_shadcn": [
      "/app/frontend/src/components/ui/badge.jsx",
      "/app/frontend/src/components/ui/button.jsx",
      "/app/frontend/src/components/ui/card.jsx",
      "/app/frontend/src/components/ui/dialog.jsx",
      "/app/frontend/src/components/ui/select.jsx",
      "/app/frontend/src/components/ui/calendar.jsx",
      "/app/frontend/src/components/ui/tabs.jsx",
      "/app/frontend/src/components/ui/table.jsx",
      "/app/frontend/src/components/ui/popover.jsx",
      "/app/frontend/src/components/ui/sheet.jsx",
      "/app/frontend/src/components/ui/separator.jsx",
      "/app/frontend/src/components/ui/sonner.jsx"
    ],
    "others": ["Recharts", "Framer Motion"]
  },
  "instructions_to_main_agent": {
    "priority": [
      "Implement tokens in :root per css_tokens.root_vars_snippet in /src/index.css",
      "Import fonts and set font stacks in Tailwind config or global CSS",
      "Create StatusBadge.js and FiltersBar.js scaffolds using .js (not .tsx)",
      "Build page shells and routes per layout_and_pages.routes",
      "Apply data-testid on all interactive elements per testing.data_testid_rule",
      "Use shadcn/ui components defined in components.paths and usage_map",
      "Respect Gradient Restriction Rule when styling sections"
    ],
    "copy_and_tone": "Use B2B phrasing: 'capacity sharing', 'request', 'match', 'counterparty hotel'. Never use booking/consumer vocabulary.",
    "accessibility_testing": "Run A11y checks for contrast and keyboard navigation. Ensure Dialog and Sheet focus management.",
    "responsive": "Mobile-first; use Sheet for navigation and filters on small screens. Keep tables scrollable x-axis with sticky headers on md+."
  }
}


<General UI UX Design Guidelines>  
    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms
    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text
   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json

 **GRADIENT RESTRICTION RULE**
NEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc
NEVER use dark gradients for logo, testimonial, footer etc
NEVER let gradients cover more than 20% of the viewport.
NEVER apply gradients to text-heavy content or reading areas.
NEVER use gradients on small UI elements (<100px width).
NEVER stack multiple gradient layers in the same viewport.

**ENFORCEMENT RULE:**
    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors

**How and where to use:**
   • Section backgrounds (not content backgrounds)
   • Hero section header content. Eg: dark to light to dark color
   • Decorative overlays and accent elements only
   • Hero section with 2-3 mild color
   • Gradients creation can be done for any angle say horizontal, vertical or diagonal

- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**

</Font Guidelines>

- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. 
   
- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.

- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.
   
- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly
    Eg: - if it implies playful/energetic, choose a colorful scheme
           - if it implies monochrome/minimal, choose a black–white/neutral scheme

**Component Reuse:**
	- Prioritize using pre-existing components from src/components/ui when applicable
	- Create new components that match the style and conventions of existing components when needed
	- Examine existing components to understand the project's component patterns before creating new ones

**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component

**Best Practices:**
	- Use Shadcn/UI as the primary component library for consistency and accessibility
	- Import path: ./components/[component-name]

**Export Conventions:**
	- Components MUST use named exports (export const ComponentName = ...)
	- Pages MUST use default exports (export default function PageName() {...})

**Toasts:**
  - Use `sonner` for toasts"
  - Sonner component are located in `/app/src/components/ui/sonner.tsx`

Use 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals.
</General UI UX Design Guidelines>