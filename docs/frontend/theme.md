# 🌈 DuckLake Synthwave Theme

A retro synthwave CLI TUI-inspired theme for the DuckLake data platform frontend.

## 🎨 Color Palette

### Dark Backgrounds
- `synthwave-deep`: #0a0a0f - Deepest dark
- `synthwave-dark`: #1a0b2e - Main background (dark purple)
- `synthwave-darker`: #16213e - Secondary dark
- `synthwave-purple`: #240046 - UI element background
- `synthwave-indigo`: #3c096c - Accent background

### Neon Colors
- `synthwave-pink`: #ff006e - Primary accent (hot pink)
- `synthwave-cyan`: #00f5ff - Secondary accent (cyan)
- `synthwave-green`: #39ff14 - Success/online status
- `synthwave-orange`: #ff9500 - Warning states
- `synthwave-yellow`: #ffff00 - Attention/pending

### Mid-tones
- `synthwave-violet`: #7209b7 - Subtle accent
- `synthwave-blue`: #560bad - Link states
- `synthwave-teal`: #277da1 - Alternative accent

## 🔮 Special Effects

### Animations
- `animate-glow` - Pulsing neon glow effect
- `animate-flicker` - Terminal flicker simulation
- `animate-pulse-neon` - Smooth neon pulse
- `animate-scan-line` - Moving scan line effect

### Box Shadows
- `shadow-neon-cyan` - Cyan neon glow
- `shadow-neon-pink` - Pink neon glow
- `shadow-neon-green` - Green neon glow
- `shadow-terminal` - Terminal border effect

### Typography
- `font-cyber` - Orbitron font family (cyberpunk headers)
- `font-mono` - JetBrains Mono (terminal text)

## 🖥️ Component Classes

### Terminal Components
```tsx
<div className="terminal">
  <div className="terminal-content">
    {/* Your terminal content */}
  </div>
</div>
```

### Synthwave Cards
```tsx
<div className="synthwave-card">
  {/* Card content with automatic glass morphism */}
</div>
```

### Status Indicators
```tsx
<span className="status-online">ONLINE</span>
<span className="status-warning">WARNING</span>
<span className="status-error">ERROR</span>
<span className="status-offline">OFFLINE</span>
```

### Neon Text
```tsx
<h1 className="text-neon-cyan">Cyberpunk Title</h1>
<p className="text-neon-pink">Hot pink accent</p>
<span className="text-neon-green">Success message</span>
```

## 🎛️ Global Effects

### Body Effects
- Gradient background from dark purple to indigo
- Moving scan line across the screen
- Subtle vertical line pattern overlay
- Custom neon scrollbars

### Grid Overlay
```tsx
<div className="grid-overlay">
  {/* Content with subtle grid pattern */}
</div>
```

### Loading States
```tsx
<div className="loading-border">
  {/* Element with pulsing border */}
</div>
```

## 🛠️ Customization

### Custom Neon Colors
Add new neon colors to `tailwind.config.ts`:

```typescript
colors: {
  synthwave: {
    'custom': '#your-color',
  }
}
```

### Custom Animations
Add new keyframes in `tailwind.config.ts`:

```typescript
keyframes: {
  'your-animation': {
    '0%': { /* start state */ },
    '100%': { /* end state */ },
  }
}
```

### Terminal Variants
Create custom terminal styles in `globals.css`:

```css
.terminal-variant {
  background: rgba(10, 10, 15, 0.95);
  border: 1px solid #your-color;
  /* Your custom styling */
}
```

## 📱 Responsive Design

The theme automatically adapts to different screen sizes:
- Mobile: Reduced font sizes, simplified effects
- Tablet: Medium effects, optimized layouts
- Desktop: Full effects, maximum visual impact

## 🎯 Performance

- CSS animations use GPU acceleration
- Backdrop filters limited on mobile
- Efficient neon glow implementations
- Optimized for 60fps performance

## 🎨 Theme Integration

All components automatically inherit the synthwave styling:
- Buttons get neon gradient backgrounds
- Inputs have glowing focus states  
- Cards use glass morphism effects
- Text elements get proper neon colors

## 🔧 Development Tips

1. Use `text-synthwave-cyan` for primary text
2. Use `text-synthwave-pink` for accents and CTAs
3. Use `terminal` class for code/log displays
4. Use `synthwave-card` for panels and containers
5. Add `animate-pulse-neon` to important headings

## 🌟 Examples

### Dashboard Header
```tsx
<div className="terminal p-6 rounded-lg">
  <div className="terminal-content">
    <h1 className="text-4xl font-cyber font-black text-synthwave-cyan animate-pulse-neon">
      DUCKLAKE CONTROL
    </h1>
    <p className="text-synthwave-cyan/60 font-mono">
      &gt; SYSTEM OPERATIONAL
    </p>
  </div>
</div>
```

### Status Card
```tsx
<div className="synthwave-card loading-border">
  <div className="p-6">
    <div className="flex items-center gap-2">
      <div className="w-3 h-3 bg-synthwave-green rounded-full animate-pulse" />
      <span className="text-synthwave-green font-mono font-bold">
        SYSTEM ONLINE
      </span>
    </div>
  </div>
</div>
```

Enjoy your cyberpunk data platform! 🚀✨ 