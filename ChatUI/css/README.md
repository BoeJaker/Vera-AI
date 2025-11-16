# ChatUI Stylesheets

## Overview

CSS files for styling Vera's web interface components.

## Structure

Styles are organized by component and follow a modular approach for maintainability.

## Conventions

### Naming
- Use kebab-case for class names: `.chat-message`
- Prefix component styles: `.toolchain-progress`
- Use semantic names: `.primary-button` not `.blue-button`

### Organization
```css
/* Component: Chat Interface */
.chat-container { }
.chat-message { }
.chat-input { }

/* Component: Graph Visualizer */
.graph-container { }
.graph-node { }
.graph-edge { }
```

### Theming
Variables for theme customization:
```css
:root {
    --primary-color: #4A90E2;
    --background-color: #FFFFFF;
    --text-color: #333333;
    --accent-color: #FF6B6B;
    --border-radius: 8px;
    --spacing-unit: 8px;
}

[data-theme="dark"] {
    --background-color: #1E1E1E;
    --text-color: #E0E0E0;
}
```

## Responsive Design

Mobile-first approach with breakpoints:
```css
/* Mobile: default */
.container { width: 100%; }

/* Tablet: 768px+ */
@media (min-width: 768px) {
    .container { width: 750px; }
}

/* Desktop: 1024px+ */
@media (min-width: 1024px) {
    .container { width: 960px; }
}
```

## Accessibility

- Sufficient color contrast (WCAG AA)
- Focus indicators for keyboard navigation
- Readable font sizes (minimum 14px)
- Clear visual hierarchies

---

**Related:** [ChatUI](../README.md), [Theme Manager](../js/theme.js)
