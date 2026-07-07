---
name: "SPBE RAG System"
description: "Formal internal BSSN design system for SPBE legal consultation, document review, and source-backed RAG workflows."
colors:
  primary-navy: "#1a3a6b"
  primary-navy-dark: "#122d57"
  primary-navy-hover: "#2c5282"
  action-blue: "#0b4abf"
  gold-accent: "#c9a84c"
  gold-hover: "#d4b55e"
  cream-bg: "#f8f7f4"
  cream-muted: "#f0ece4"
  white: "#ffffff"
  surface-blue: "#f6f9fd"
  surface-blue-muted: "#edf3fb"
  ink: "#333333"
  ink-strong: "#071f45"
  ink-muted: "#888888"
  ink-light: "#bbbbbb"
  border: "#e8e0d0"
  border-light: "#f5f2ee"
  border-blue: "#dce6f3"
  success-bg: "#edf7f2"
  success-text: "#2d7a4f"
  warning-bg: "#fdf8ee"
  warning-text: "#8b7355"
  danger: "#c0392b"
typography:
  display:
    fontFamily: "Playfair Display, Georgia, serif"
    fontSize: "clamp(34px, 4.5vw, 58px)"
    fontWeight: 700
    lineHeight: 1.03
    letterSpacing: "-1.1px"
  headline:
    fontFamily: "Playfair Display, Georgia, serif"
    fontSize: "clamp(24px, 3vw, 36px)"
    fontWeight: 700
    lineHeight: 1.18
    letterSpacing: "-0.5px"
  title:
    fontFamily: "IBM Plex Sans, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 700
    lineHeight: 1.35
  body:
    fontFamily: "IBM Plex Sans, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.65
  body-serif:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "IBM Plex Sans, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.5px"
rounded:
  xs: "2px"
  sm: "4px"
  md: "14px"
  lg: "20px"
  xl: "28px"
  hero: "32px"
spacing:
  xxs: "4px"
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  page-x: "24px"
  page-y: "34px"
components:
  button-primary:
    backgroundColor: "{colors.primary-navy}"
    textColor: "{colors.white}"
    rounded: "{rounded.md}"
    padding: "0 22px"
    height: "46px"
    typography: "{typography.label}"
  button-secondary:
    backgroundColor: "{colors.white}"
    textColor: "{colors.primary-navy-dark}"
    rounded: "{rounded.md}"
    padding: "0 22px"
    height: "46px"
    typography: "{typography.label}"
  card-surface:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink-strong}"
    rounded: "{rounded.lg}"
    padding: "22px"
  nav-topbar:
    backgroundColor: "{colors.primary-navy}"
    textColor: "{colors.white}"
    padding: "10px 32px"
  input-field:
    backgroundColor: "{colors.cream-bg}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xs}"
    padding: "12px 16px"
---

# Design System: SPBE RAG System

## 1. Overview

**Creative North Star: "Ruang Arsip yang Terang"**

The interface should feel like an internal government reading room: orderly, quiet, trustworthy, and ready for careful work. It is not a public marketing site and it is not an AI novelty surface. The design serves legal consultation, source review, document management, and accountable internal workflows.

The product uses restrained navy, white, cream, and gold to signal institutional confidence without overwhelming the user. The strongest surfaces are those that make source-backed reasoning visible: the Home dashboard explains the service, the Chat evidence panel anchors answers to references, and document workflows keep indexing state visible.

This system explicitly rejects the PRODUCT.md anti-references: generic AI SaaS visuals, overly busy decoration, public/commercial promotion, and any pattern that hides accountability.

**Key Characteristics:**

- Formal, calm, and trustworthy before expressive or playful.
- Source-first: visual hierarchy should lead users toward rujukan, evidence, and verification.
- Restrained color: navy carries structure, gold marks importance, white/cream preserve reading comfort.
- Product consistency over surprise: repeated controls should look and behave the same across Home, Chat, Login, and Documents.
- Accessible by default: strong contrast, keyboard-visible states, reduced motion alternatives, and clear Bahasa Indonesia.

## 2. Colors

The palette is a restrained government navy system with a gold institutional accent and quiet paper-like neutrals.

### Primary

- **Institutional Navy** (`primary-navy`): used for topbar, primary brand identity, active navigation, and high-confidence actions.
- **Deep Service Navy** (`primary-navy-dark`): used for darker application shells such as the chat sidebar and high-emphasis workflow panels.
- **Operational Blue** (`action-blue`): used sparingly for chat-specific highlights, primary interface emphasis, and source/answer accents.

### Secondary

- **Archive Gold** (`gold-accent`): used for identity marks, trusted emphasis, current state, and official-looking highlights. It must remain rare enough to feel meaningful.
- **Gold Hover** (`gold-hover`): used only for hover states on gold controls.

### Neutral

- **Government Paper** (`cream-bg`): default app background and calm reading field.
- **Muted Paper** (`cream-muted`): disabled or low-emphasis surfaces.
- **White Surface** (`white`): cards, modals, form fields, chat panels, and document tables.
- **Cool Landing Surface** (`surface-blue`, `surface-blue-muted`): Home dashboard atmospheric backgrounds only.
- **Ink Strong** (`ink-strong`): headings, primary text on light surfaces, and critical labels.
- **Ink** (`ink`): default body text.
- **Muted Ink** (`ink-muted`): metadata, helper text, secondary labels.
- **Light Ink** (`ink-light`): tertiary hints only; never use for essential body copy.
- **Warm Border** (`border`, `border-light`): legacy document/login borders and dividers.
- **Blue Border** (`border-blue`): modern Home and evidence card borders.

### Named Rules

**The Rujukan Before Accent Rule.** Gold and blue accents are earned by source, state, or primary action. Decoration alone does not earn accent color.

**The Muted Text Rule.** `ink-light` is prohibited for required instructions, labels, or legal caveats. Use `ink-muted` at minimum, and move toward `ink` when contrast is uncertain.

## 3. Typography

**Display Font:** Playfair Display, with Georgia fallback.  
**Body Font:** Source Serif 4 for selected reading-heavy prose, with Georgia fallback.  
**UI Font:** IBM Plex Sans, with system-ui fallback.

**Character:** The pairing creates a formal legal-institutional voice: Playfair gives headings authority, IBM Plex Sans keeps product controls clear, and Source Serif supports longer chat/document text where reading comfort matters.

### Hierarchy

- **Display** (700, fluid 34-58px, tight line-height): Home hero and major landing moments only.
- **Headline** (700, fluid 24-36px): section-level Home headings and major empty/welcome states.
- **Title** (700, 16-24px): cards, panels, modals, page titles, and chat evidence headings.
- **Body** (400, 13-16px, 1.55-1.75): UI copy, card descriptions, helper text, and panel explanations.
- **Body Serif** (400, 13-14px): chat prose, longer welcome descriptions, and document explanatory text.
- **Label** (600-800, 8-12px, tracked): short badges, nav labels, stepper labels, and system metadata.

### Named Rules

**The Product Label Rule.** Uppercase labels are allowed only for short operational markers such as status, stepper labels, and metadata. Body copy must never be uppercase.

**The Display Restraint Rule.** Playfair Display belongs to brand, headings, and legal emphasis. Buttons, form labels, dense tables, and controls use IBM Plex Sans.

## 4. Elevation

The system uses hybrid depth: legacy pages rely on flat borders and small shadows, while the redesigned Home uses softer ambient shadows for modern hierarchy. Depth should clarify containment and state, not create decorative glass layers.

### Shadow Vocabulary

- **Ambient Home Panel** (`0 18px 40px rgba(12, 43, 84, 0.08)`): elevated Home cards, hero panels, FAQ items, and final CTA surfaces.
- **Hero Lift** (`0 28px 70px rgba(12, 43, 84, 0.13)`): one-per-page hero container only.
- **Chat Bubble Lift** (`0 10px 28px rgba(12, 43, 84, 0.06)`): assistant answer bubble and source-backed message surfaces.
- **Modal Lift** (`0 8px 32px rgba(26, 58, 107, 0.15)`): blocking overlays and confirmation modals.
- **Toast Lift** (`0 4px 16px rgba(0,0,0,0.15)`): transient system feedback.

### Named Rules

**The One Hero Rule.** Only the main page hero may use the strongest shadow and largest radius. Reusing hero treatment on every section makes the product feel decorative.

**The Border First Rule.** Dense product workflows start with borders and tonal layers. Add shadow only when hierarchy or overlay behavior needs it.

## 5. Components

### Buttons

- **Shape:** legacy controls use square institutional corners (`2-4px`); modern Home CTAs use rounded confidence (`14px`). Future work should converge these into a documented variant split rather than mixing accidentally.
- **Primary:** navy-to-blue on Home (`primary-navy` to `action-blue`) or gold in legacy login/upload contexts. Primary buttons must have verb-object labels in Bahasa Indonesia.
- **Hover / Focus:** hover may use subtle lift (`translateY(-1px/-2px)`) and color deepening. Focus must be visible with border or ring; invisible focus is forbidden.
- **Secondary / Ghost:** white or transparent backgrounds, navy text, visible border, no filled accent unless selected.

### Chips

- **Style:** pill chips use white or pale blue backgrounds, blue/navy text, 1px border, and compact label typography.
- **State:** source chips and trust chips are informational, not buttons. If clickable, they must receive visible hover and focus states.

### Cards / Containers

- **Corner Style:** Home cards use soft modern radii (`18-28px`); legacy document/login cards use tighter radii (`3-4px`). Future normalization should preserve product calm while reducing this mismatch.
- **Background:** white is the default surface; blue-tinted surfaces are reserved for Home hero, chat preview, and answer evidence context.
- **Shadow Strategy:** use Ambient Home Panel only for high-level dashboard cards. Dense tables, modals, and upload zones should remain flatter.
- **Border:** 1px borders are the default containment mechanism. Thick one-sided accent borders are prohibited except as temporary legacy states to be polished.
- **Internal Padding:** compact controls use `8-14px`; cards use `20-24px`; hero/CTA containers use `28-54px` depending on breakpoint.

### Inputs / Fields

- **Style:** light paper background, 1px border, compact radius, and clear disabled states.
- **Focus:** border shifts to gold or navy with subtle ring. The ring must be visible on keyboard focus and not rely on color alone.
- **Error / Disabled:** error states use red text plus border/background affordance; disabled fields reduce contrast but must remain readable.

### Navigation

- **Topbar:** dark navy, compact spacing, gold active state, formal brand mark. User/account details must remain readable and not collapse into low-opacity text.
- **Home anchor nav:** sticky white translucent anchor rail for section jumping; on small screens it scrolls horizontally.
- **Sidebar:** dark navy task shell for chat sessions, with gold primary action and compact session grouping.

### Evidence Panel

The evidence panel is the signature product component. It separates answers from rujukan, uses source count/state, and shows retrieval context. Preserve this pattern: every AI answer workflow should make source review visible and easy to reach.

### Document Table

The table is a dense product component, not a marketing card grid. It should prioritize scan speed, truncation, status clarity, and mobile conversion to stacked rows when width is constrained.

## 6. Do's and Don'ts

### Do:

- **Do** keep the interface formal, calm, and trustworthy. Product UI must serve legal/SPBE work before visual novelty.
- **Do** use navy for structure, gold for rare institutional emphasis, and white/cream for reading surfaces.
- **Do** make rujukan and evidence visible before confidence. If an answer has sources, the UI should guide the user toward them.
- **Do** maintain WCAG AA as the minimum for text contrast, keyboard focus, semantic structure, and reduced motion.
- **Do** document every new reusable pattern in the same visual vocabulary: button, card, status, table, source panel, and form control.

### Don't:

- **Don't** create a generic AI SaaS look: gradient-heavy hero sections, endless identical card grids, buzzword copy, or decorative glass effects.
- **Don't** make the interface too busy. Decoration, animation, and novelty must never distract from legal text and source review.
- **Don't** make authenticated internal screens feel like public/commercial marketing pages.
- **Don't** hide accountability. Disclaimers, source state, retrieval state, and legal limitations must remain visible.
- **Don't** use `border-left` or `border-right` greater than `1px` as a colored stripe on cards, suggestions, or alerts. Replace with full borders, background tint, icons, or structured metadata.
- **Don't** animate layout dimensions such as width/height for routine progress or navigation state. Use transform, opacity, or instant state changes.
- **Don't** rely on low-opacity white text for essential nav/account information. If users need it, it must be readable.
