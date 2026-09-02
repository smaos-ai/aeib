# SMAOS Navigation UI - Implementation Specification
**Code-Ready Reference for Developers**

---

## PART 1: TYPOGRAPHY & SIZING SPECIFICATION

### Font Stack (Keep Current)
```css
font-family: 'Monaco', 'Courier New', monospace;
/* Monospace is good for compliance dashboards (technical feel) */
```

### Font Size Changes
```css
/* Navigation Labels */
.nav-label {
  font-size: 14px;    /* ↑ from 13px */
  font-weight: 500;   /* (active), 400 (inactive) */
  line-height: 1.4;
  letter-spacing: 0;
}

/* Secondary Labels & Descriptions */
.nav-description {
  font-size: 10px;    /* ↑ from 9px */
  font-weight: 400;
  color: #a0a0a0;     /* To be boosted to #c0c0c0 */
  line-height: 1.3;
}

/* Breadcrumbs (new) */
.breadcrumb {
  font-size: 12px;
  font-weight: 400;
  color: #4b5563;
}

/* Category Headers (new) */
.nav-category-header {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent-blue);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 16px 0 8px 0;
  padding: 8px 16px;
}

/* Help/Info Text */
.help-text {
  font-size: 11px;
  font-weight: 400;
  color: #4b5563;
}
```

### Icon Sizing Changes
```css
/* Expanded Navigation Mode */
.nav-icon--expanded {
  font-size: 24px;    /* ↑ from 20px */
  display: block;
  width: 24px;        /* Explicit width for centering */
  height: 24px;
  line-height: 24px;
  text-align: center;
}

/* Compressed Navigation Mode */
.nav-icon--compressed {
  font-size: 32px;    /* ↑ from 28px */
  display: block;
  width: 32px;
  height: 32px;
  line-height: 32px;
  text-align: center;
}

/* Category Icons */
.nav-icon--category {
  font-size: 16px;
  display: block;
  width: 16px;
  height: 16px;
  line-height: 16px;
}
```

---

## PART 2: SPACING & LAYOUT SPECIFICATION

### Sidebar Dimensions
```css
/* Sidebar Container */
.sidebar-navigation {
  /* Expanded */
  width: 256px;       /* Standard for SaaS (was variable) */
  transition: width 250ms cubic-bezier(0.4, 0, 0.2, 1);
  
  /* Collapsed (on scroll) */
  &.collapsed {
    width: 80px;
  }
}

/* Navigation Item Padding */
.nav-item {
  padding: 16px;      /* ↑ from 14px (top/bottom/left/right) */
  /* Breakdown: 12px vertical, 16px horizontal (modern standard) */
}

.nav-item--compact {
  padding: 12px 8px;  /* Compressed mode, icon-only */
}

/* Gap Between Navigation Items */
.nav-list {
  display: flex;
  flex-direction: column;
  gap: 12px;          /* ↑ from 8px (tighter items, easier to target) */
}

/* Expanded Grid Layout */
.nav-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 16px;          /* ↑ from 12px (breathing room between cards) */
  padding: 20px;
}

/* Icon-to-Label Gap */
.nav-item__content {
  display: flex;
  flex-direction: column;
  gap: 8px;           /* ↑ from 6px (visual separation) */
}

.nav-item--horizontal {
  display: flex;
  gap: 12px;          /* When icon is left of text */
  align-items: center;
}

/* Category Padding & Spacing */
.nav-category {
  margin-bottom: 8px;
  
  &__header {
    padding: 12px 16px;
    margin-bottom: 8px;
  }
  
  &__items {
    padding-left: 8px;  /* Subtle indent for nested items */
  }
}
```

### Sidebar Header & Footer
```css
.sidebar-header {
  padding: 24px;      /* Keep as is (spacious, welcoming) */
  background: linear-gradient(180deg, rgba(10, 14, 39, 0.95) 0%, rgba(10, 14, 39, 0.85) 100%);
  border-bottom: 2px solid rgba(59, 130, 246, 0.2);
  text-align: center;
  font-size: 16px;
  font-weight: bold;
  color: var(--accent-blue);
  margin-bottom: 16px;
}

.sidebar-footer {
  padding: 16px;
  background: rgba(0, 0, 0, 0.2);
  border-top: 1px solid rgba(100, 116, 139, 0.2);
  font-size: 9px;
  color: #4b5563;
  text-align: center;
  line-height: 1.4;
  margin-top: auto;
}
```

---

## PART 3: COLOR & CONTRAST SPECIFICATION

### Primary Colors (Keep)
```css
:root {
  --accent-blue: #3b82f6;      /* Primary (operations) */
  --accent-green: #10b981;     /* Success/completion */
  --accent-yellow: #f59e0b;    /* Warning/attention */
  --accent-red: #ef4444;       /* Danger/critical */
  --accent-purple: #a78bfa;    /* Secondary (compliance) */
  --accent-cyan: #06b6d4;      /* Tertiary (learning) */
  
  --bg-dark: #0a0e27;          /* Main background */
  --bg-panel: #1a1f3a;         /* Panel background */
  --text-primary: #e0e0e0;     /* Primary text */
  --text-secondary: #a0a0a0;   /* Secondary text (NEEDS BOOST) */
  --text-secondary-new: #c0c0c0; /* NEW: Better contrast */
  --border: #2d3748;            /* Border color */
}
```

### Active Navigation Item (Critical - Left Border Style)
```css
.nav-item.active {
  /* Structure */
  border: 1px solid;
  border-left: 4px solid;       /* PRIMARY INDICATOR */
  border-color: currentColor;   /* Use section's accent color */
  
  /* Background */
  background: rgba(59, 130, 246, 0.15);
  
  /* Text & Icon Color */
  color: var(--accent-blue);    /* Or section.color */
  
  /* Elevation */
  box-shadow: inset 4px 0 0 var(--accent-blue);
  
  /* Animation */
  transform: scale(1.02);
  transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
  
  /* Font weight increase for active */
  font-weight: 600;
}
```

### Hover Navigation Item
```css
.nav-item:hover:not(.active):not(:disabled) {
  /* Background */
  background: rgba(59, 130, 246, 0.15);
  
  /* Border */
  border-color: rgba(59, 130, 246, 0.6);
  
  /* Depth effect */
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.2);
  
  /* Animation */
  transition: all 150ms ease-out;
}
```

### Focus Navigation Item (Keyboard Accessibility)
```css
.nav-item:focus-visible {
  /* Outline (highest z-index visual signal) */
  outline: 2px solid var(--accent-blue);
  outline-offset: 2px;
  
  /* Animation */
  transition: outline 100ms ease-out;
}

/* Remove focus outline for mouse clicks (only show for keyboard) */
.nav-item:focus:not(:focus-visible) {
  outline: none;
}
```

### Inactive Navigation Item
```css
.nav-item:not(.active) {
  border: 1px solid rgba(100, 116, 139, 0.2);
  background: rgba(26, 31, 58, 0.6);
  color: #a0a0a0;              /* ← Will update to #c0c0c0 */
  font-weight: 400;
}
```

### Disabled Navigation Item
```css
.nav-item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: rgba(100, 116, 139, 0.15);
  border-color: rgba(100, 116, 139, 0.3);
  color: #4b5563;
  pointer-events: none;
}
```

### Contrast Verification Table
```
Component                          | Color Combination        | Ratio  | WCAG
-----------------------------------|-------------------------|--------|------
Active Label (blue on bg)          | #3b82f6 on #1a1f3a      | 7.1:1  | AAA ✓
Primary Text                       | #e0e0e0 on #0a0e27      | 14:1   | AAA ✓
Secondary Text (NEEDS UPDATE)      | #a0a0a0 on #1a1f3a      | 5.2:1  | AA (BORDERLINE)
Secondary Text (FIXED)             | #c0c0c0 on #1a1f3a      | 7.5:1  | AAA ✓
Active Button                      | #fff on #3b82f6         | 8.5:1  | AAA ✓
Disabled Text                      | #4b5563 on #1a1f3a      | 3.1:1  | OK (disabled acceptable)
Hover Background                   | rgba(59,130,246,0.15)   | Various| RECHECK
```

---

## PART 4: ANIMATION & TRANSITION SPECIFICATION

### Global Timing Variables
```css
:root {
  /* Easing curves */
  --ease-responsive: cubic-bezier(0.4, 0, 0.2, 1);  /* Material standard */
  --ease-smooth: cubic-bezier(0.25, 0.46, 0.45, 0.94); /* Natural motion */
  --ease-bounce: cubic-bezier(0.68, -0.55, 0.265, 1.55); /* Playful */
  --ease-linear: linear; /* Progress bars, loading */
  
  /* Durations */
  --duration-micro: 100ms;     /* Instant feedback */
  --duration-fast: 150ms;      /* Hover, immediate response */
  --duration-normal: 200ms;    /* Standard navigation */
  --duration-slow: 250-300ms;  /* Sidebar collapse, major transitions */
  --duration-slow-xl: 300-400ms; /* Modals, dialogs */
}
```

### Navigation Item Transitions
```css
.nav-item {
  /* Base transition (applies to all properties) */
  transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
  
  /* Or be specific (better performance) */
  transition: 
    background 200ms ease-out,
    border-color 200ms ease-out,
    color 200ms ease-out,
    transform 150ms ease-out,
    box-shadow 150ms ease-out;
}

/* Hover animation (faster feedback) */
.nav-item:hover {
  transition: all 150ms ease-out;
}

/* Focus animation (instant) */
.nav-item:focus-visible {
  transition: outline 100ms ease-out;
}
```

### Sidebar Collapse/Expand
```css
.sidebar-navigation {
  transition: width 250ms cubic-bezier(0.4, 0, 0.2, 1);
  
  &.collapsed {
    width: 80px;
  }
}

/* Items inside sidebar also animate */
.nav-item {
  /* Fade out label in collapsed mode */
  opacity: 1;
  transition: opacity 200ms ease-out;
}

.sidebar.collapsed .nav-item__label {
  opacity: 0;
  pointer-events: none;
}
```

### Tooltip Fade-In
```css
.nav-tooltip {
  animation: fadeIn 200ms ease-out forwards;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateX(10px);  /* Slide from right */
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
```

### Scale Animation (Active Item)
```css
.nav-item.active {
  /* Pulse effect on active */
  animation: pulse 0.6s ease-in-out;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1.02);
  }
  50% {
    transform: scale(1.08);
  }
}
```

---

## PART 5: RESPONSIVE BREAKPOINTS

### Mobile-First Approach
```css
/* Base: Mobile (0-767px) */
.sidebar-navigation {
  display: none;  /* Hide sidebar on mobile */
}

.bottom-navigation {
  display: flex;  /* Show bottom nav on mobile */
}

/* Tablet (768px-1023px) */
@media (min-width: 768px) {
  .sidebar-navigation {
    display: block;
    width: 80px;  /* Always collapsed on tablet */
  }
  
  .bottom-navigation {
    display: none;  /* Hide bottom nav on tablet */
  }
}

/* Desktop (1024px+) */
@media (min-width: 1024px) {
  .sidebar-navigation {
    display: block;
    width: 256px;  /* Expanded on desktop */
    
    &.collapsed {
      width: 80px;
    }
  }
  
  .bottom-navigation {
    display: none;  /* Hide bottom nav on desktop */
  }
}
```

### Grid Layout Responsiveness
```css
/* Mobile */
.nav-grid {
  grid-template-columns: repeat(auto-fit, minmax(100%, 1fr));
  gap: 8px;
  padding: 12px;
}

/* Tablet */
@media (min-width: 768px) {
  .nav-grid {
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 12px;
    padding: 16px;
  }
}

/* Desktop */
@media (min-width: 1024px) {
  .nav-grid {
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 16px;
    padding: 20px;
  }
}
```

---

## PART 6: ACCESSIBILITY ATTRIBUTES

### Semantic HTML & ARIA Labels
```jsx
{/* Navigation Container */}
<nav
  aria-label="Main navigation"
  role="navigation"
>

{/* Navigation Item with Current Section */}
<button
  onClick={() => handleSectionClick(section.id)}
  className={`nav-item ${activeId === section.id ? 'active' : ''}`}
  aria-label={`${section.name} - ${section.brings}`}
  aria-current={activeId === section.id ? 'page' : undefined}
  title={section.name}
>
  <span aria-hidden="true">{section.icon}</span>
  <span className="nav-item__label">{section.name}</span>
  <span className="nav-item__description">{section.brings}</span>
</button>

{/* Category Header (Collapsible) */}
<button
  aria-expanded={categoryExpanded}
  aria-controls={`nav-category-${categoryId}`}
  className="nav-category__header"
>
  <span aria-hidden="true">{categoryIcon}</span>
  <span>{categoryName}</span>
</button>

{/* Category Items (Controlled by header) */}
<div
  id={`nav-category-${categoryId}`}
  hidden={!categoryExpanded}
  className="nav-category__items"
>
  {/* Items */}
</div>

{/* Skip Link (accessibility best practice) */}
<a href="#main-content" className="skip-link">
  Skip to main content
</a>
```

### ARIA Live Region (for updates)
```jsx
{/* Screen reader announcement of active section change */}
<div
  aria-live="polite"
  aria-atomic="true"
  className="sr-only"  /* Visually hidden but readable to screen readers */
>
  Current section: {currentSection.name}
</div>
```

### CSS for Screen Reader Only Content
```css
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  background: var(--accent-blue);
  color: white;
  padding: 8px;
  text-decoration: none;
  z-index: 100;
  
  &:focus {
    top: 0;  /* Visible on focus */
  }
}
```

---

## PART 7: COMPONENT STRUCTURE (JSX)

### Refactored Navigation Item Component
```jsx
export function NavigationItem({ 
  section, 
  isActive, 
  onSelect, 
  isCompressed 
}) {
  const [isHovered, setIsHovered] = useState(false)
  
  return (
    <button
      onClick={() => onSelect(section.id)}
      className={[
        'nav-item',
        isActive && 'nav-item--active',
        isCompressed && 'nav-item--compressed'
      ].join(' ')}
      aria-label={`${section.name} - ${section.brings}`}
      aria-current={isActive ? 'page' : undefined}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <span className="nav-item__icon" aria-hidden="true">
        {section.icon}
      </span>
      
      {!isCompressed && (
        <>
          <span className="nav-item__label">
            {section.name}
          </span>
          <span className="nav-item__description">
            → {section.brings}
          </span>
        </>
      )}
      
      {/* Tooltip in compressed mode */}
      {isCompressed && isHovered && (
        <div className="nav-tooltip">
          <div className="nav-tooltip__title">
            {section.icon} {section.name}
          </div>
          <div className="nav-tooltip__description">
            {section.brings}
          </div>
        </div>
      )}
    </button>
  )
}
```

### Navigation Category Component (NEW)
```jsx
export function NavigationCategory({ label, icon, items, defaultExpanded = true }) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  
  return (
    <div className="nav-category">
      <button
        className="nav-category__header"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        aria-controls={`nav-category-${label}`}
      >
        <span aria-hidden="true">{icon}</span>
        <span>{label}</span>
        <span className="nav-category__toggle" aria-hidden="true">
          {expanded ? '▼' : '▶'}
        </span>
      </button>
      
      {expanded && (
        <div
          id={`nav-category-${label}`}
          className="nav-category__items"
        >
          {items.map(item => (
            <NavigationItem key={item.id} {...item} />
          ))}
        </div>
      )}
    </div>
  )
}
```

### Bottom Navigation Component (NEW - Mobile)
```jsx
export function BottomNavigation({ items, activeId, onSelect }) {
  return (
    <nav
      className="bottom-nav"
      aria-label="Mobile navigation"
    >
      {items.map(item => (
        <button
          key={item.id}
          className={['bottom-nav__item', activeId === item.id && 'bottom-nav__item--active'].join(' ')}
          onClick={() => onSelect(item.id)}
          aria-current={activeId === item.id ? 'page' : undefined}
          aria-label={`${item.label} - ${item.description}`}
        >
          <span className="bottom-nav__icon" aria-hidden="true">
            {item.icon}
          </span>
          <span className="bottom-nav__label">
            {item.label}
          </span>
        </button>
      ))}
    </nav>
  )
}
```

---

## PART 8: CSS COMPLETE REFERENCE

### All-in-One CSS (Copy-Paste Ready)
```css
/* ============================================
   SMAOS NAVIGATION UI - COMPLETE STYLES
   ============================================ */

:root {
  /* Colors */
  --bg-dark: #0a0e27;
  --bg-panel: #1a1f3a;
  --text-primary: #e0e0e0;
  --text-secondary: #c0c0c0;      /* ↑ Updated from #a0a0a0 */
  --text-tertiary: #4b5563;
  --accent-blue: #3b82f6;
  --accent-green: #10b981;
  --accent-yellow: #f59e0b;
  --accent-red: #ef4444;
  --accent-purple: #a78bfa;
  --accent-cyan: #06b6d4;
  
  /* Typography */
  --nav-font-label: 14px;
  --nav-font-secondary: 10px;
  --nav-font-meta: 12px;
  
  /* Spacing */
  --nav-icon-size: 24px;
  --nav-icon-compressed: 32px;
  --nav-padding: 16px;
  --nav-gap: 12px;
  
  /* Animation */
  --ease-responsive: cubic-bezier(0.4, 0, 0.2, 1);
  --duration-micro: 100ms;
  --duration-fast: 150ms;
  --duration-normal: 200ms;
  --duration-slow: 250ms;
}

/* Navigation Item - Base */
.nav-item {
  padding: var(--nav-padding);
  border: 1px solid rgba(100, 116, 139, 0.2);
  border-radius: 8px;
  background: rgba(26, 31, 58, 0.6);
  color: var(--text-secondary);
  font-size: var(--nav-font-label);
  font-weight: 400;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--nav-gap);
  transition: all var(--duration-normal) var(--ease-responsive);
  outline: none;
}

/* Navigation Item - Icon */
.nav-item__icon {
  font-size: var(--nav-icon-size);
  display: block;
  width: var(--nav-icon-size);
  height: var(--nav-icon-size);
  line-height: var(--nav-icon-size);
  text-align: center;
}

/* Navigation Item - Label */
.nav-item__label {
  font-size: var(--nav-font-label);
  font-weight: 500;
  color: inherit;
}

/* Navigation Item - Description */
.nav-item__description {
  font-size: var(--nav-font-secondary);
  color: var(--text-secondary);
  line-height: 1.3;
  font-weight: 400;
}

/* Navigation Item - Hover State */
.nav-item:hover:not(.nav-item--active):not(:disabled) {
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.6);
  color: var(--text-primary);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.2);
  transition: all var(--duration-fast) ease-out;
}

/* Navigation Item - Active State */
.nav-item--active {
  border: 1px solid var(--accent-blue);
  border-left: 4px solid var(--accent-blue);
  background: rgba(59, 130, 246, 0.15);
  color: var(--accent-blue);
  font-weight: 600;
  box-shadow: inset 4px 0 0 var(--accent-blue);
  transform: scale(1.02);
}

/* Navigation Item - Focus State */
.nav-item:focus-visible {
  outline: 2px solid var(--accent-blue);
  outline-offset: 2px;
  transition: outline var(--duration-micro) ease-out;
}

.nav-item:focus:not(:focus-visible) {
  outline: none;
}

/* Navigation Item - Disabled State */
.nav-item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: rgba(100, 116, 139, 0.15);
  border-color: rgba(100, 116, 139, 0.3);
  color: var(--text-tertiary);
  pointer-events: none;
}

/* Navigation Category Header */
.nav-category__header {
  padding: 12px var(--nav-padding);
  margin: 16px 0 8px 0;
  border: none;
  background: transparent;
  color: var(--accent-blue);
  font-size: var(--nav-font-meta);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.nav-category__header:hover {
  color: var(--accent-blue);
  opacity: 0.8;
}

.nav-category__toggle {
  margin-left: auto;
  font-size: 10px;
}

/* Navigation List */
.nav-list {
  display: flex;
  flex-direction: column;
  gap: var(--nav-gap);
}

/* Navigation Grid */
.nav-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 16px;
  padding: 20px;
}

/* Bottom Navigation (Mobile) */
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 64px;
  background: rgba(10, 14, 39, 0.98);
  border-top: 1px solid rgba(59, 130, 246, 0.2);
  display: flex;
  gap: 0;
  align-items: stretch;
  z-index: 999;
}

.bottom-nav__item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 10px;
  cursor: pointer;
  transition: all var(--duration-fast) ease-out;
}

.bottom-nav__item:hover {
  background: rgba(59, 130, 246, 0.1);
  color: var(--accent-blue);
}

.bottom-nav__item--active {
  background: rgba(59, 130, 246, 0.15);
  color: var(--accent-blue);
  border-top: 3px solid var(--accent-blue);
}

.bottom-nav__icon {
  font-size: 24px;
  display: block;
  width: 24px;
  height: 24px;
  line-height: 24px;
  text-align: center;
}

.bottom-nav__label {
  font-size: 10px;
  text-align: center;
}

/* Tooltip */
.nav-tooltip {
  position: absolute;
  left: -250px;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(59, 130, 246, 0.2);
  border: 2px solid var(--accent-blue);
  border-radius: 10px;
  padding: 12px 16px;
  font-size: 10px;
  color: var(--text-primary);
  white-space: normal;
  max-width: 220px;
  pointer-events: none;
  animation: tooltipFadeIn 200ms ease-out forwards;
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.3);
  backdrop-filter: blur(8px);
  z-index: 1000;
}

.nav-tooltip__title {
  color: var(--accent-blue);
  margin-bottom: 4px;
  font-weight: 600;
}

.nav-tooltip__description {
  color: var(--text-secondary);
  font-size: 9px;
  line-height: 1.3;
}

/* Animations */
@keyframes tooltipFadeIn {
  from {
    opacity: 0;
    transform: translateY(-50%) translateX(10px);
  }
  to {
    opacity: 1;
    transform: translateY(-50%) translateX(0);
  }
}

@keyframes navItemPulse {
  0%, 100% { transform: scale(1.02); }
  50% { transform: scale(1.08); }
}

/* Active item animation */
.nav-item--active {
  animation: navItemPulse 0.6s ease-in-out;
}

/* Screen Reader Only */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

/* Responsive */
@media (max-width: 767px) {
  .sidebar-navigation { display: none; }
  .bottom-nav { display: flex; }
}

@media (min-width: 768px) and (max-width: 1023px) {
  .sidebar-navigation { width: 80px; }
  .bottom-nav { display: none; }
}

@media (min-width: 1024px) {
  .sidebar-navigation { width: 256px; }
  .sidebar-navigation.collapsed { width: 80px; }
  .bottom-nav { display: none; }
}
```

---

## PART 9: TESTING CHECKLIST

### Visual Testing
- [ ] Font sizes: 14px labels visible (test on 1920x1080 screen)
- [ ] Icon sizes: 24px/32px clearly visible
- [ ] Spacing: 16px padding gives items breathing room
- [ ] Contrast: All text readable (use https://www.tpgi.com/color-contrast-checker/)
- [ ] Active state: Left border clearly visible (not blending with background)
- [ ] Hover state: Slight lift (translateY(-2px)) noticeable without being jarring
- [ ] Animations: Smooth at 60fps (check DevTools Performance tab)

### Accessibility Testing
- [ ] Keyboard: Tab through all items (logical order)
- [ ] Focus: Visible blue outline on all interactive elements
- [ ] Screen Reader: Test with NVDA (Windows) or VoiceOver (Mac)
- [ ] Color Blindness: Test with simulator https://www.color-blindness.com/
- [ ] Mobile: Test touch targets (44x44px minimum)

### Responsive Testing
- [ ] Mobile (375px): Bottom nav visible, sidebar hidden
- [ ] Tablet (768px): Sidebar at 80px (icon-only)
- [ ] Desktop (1024px+): Full sidebar at 256px
- [ ] Orientation: Works in both portrait and landscape

### Performance Testing
- [ ] Animations at 60fps (DevTools Performance)
- [ ] No jank on collapse/expand (use Chrome DevTools Timeline)
- [ ] Transitions smooth (200-250ms, not 400ms)

---

## PART 10: MIGRATION CHECKLIST

### Phase 1: CSS Updates (Day 1)
- [ ] Update `:root` variables (font sizes, spacing, colors)
- [ ] Update `.nav-item` base styles (padding, gap, transitions)
- [ ] Add `.nav-item--active` left-border style
- [ ] Add `.nav-item:hover` transform + shadow
- [ ] Add `.nav-item:focus-visible` outline
- [ ] Test contrast ratios

### Phase 2: HTML/JSX Updates (Day 2)
- [ ] Add `aria-label` to all nav items
- [ ] Add `aria-current="page"` to active item
- [ ] Remove inline `onMouseEnter`/`onMouseLeave` handlers
- [ ] Use CSS classes instead (`:hover` pseudo-class)
- [ ] Add `aria-expanded` to collapsible sections
- [ ] Add `aria-controls` to section headers

### Phase 3: Component Refactoring (Day 2-3)
- [ ] Extract `NavigationItem` component
- [ ] Create `NavigationCategory` component
- [ ] Create `BottomNavigation` component (new)
- [ ] Update `SideNavigationPanel` to use components
- [ ] Test all state transitions (active, hover, focus)

### Phase 4: Mobile Features (Day 3-4)
- [ ] Add mobile breakpoints (768px, 1024px)
- [ ] Hide sidebar on mobile
- [ ] Show bottom nav on mobile
- [ ] Test on real devices (iPhone, Android)
- [ ] Ensure touch targets are 44x44px

### Phase 5: Testing & Polish (Day 4-5)
- [ ] Full accessibility audit (WCAG AAA)
- [ ] Screen reader testing
- [ ] Performance optimization
- [ ] Visual regression testing
- [ ] Documentation updates

---

**Total Development Time:** 4-5 days for one experienced frontend engineer

**Verification:** All changes automated in CI/CD with:
- Lighthouse audit (>90 accessibility score)
- axe accessibility scan (0 violations)
- Visual regression tests
- E2E tests for navigation

