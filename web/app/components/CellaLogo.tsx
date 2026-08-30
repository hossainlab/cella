import React from "react";

interface CellaLogoProps {
  size?: number;
  className?: string;
}

export default function CellaLogo({ size = 26, className = "" }: CellaLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 36 36"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Cella Logo"
      style={{ verticalAlign: "middle", flexShrink: 0 }}
    >
      <defs>
        {/* Main vibrant gradient for outer C-helix */}
        <linearGradient
          id="cella-primary-grad"
          x1="4"
          y1="4"
          x2="32"
          y2="32"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0%" stopColor="#00E5FF" />
          <stop offset="45%" stopColor="#38BDF8" />
          <stop offset="80%" stopColor="#818CF8" />
          <stop offset="100%" stopColor="#C084FC" />
        </linearGradient>

        {/* Inner core accent gradient */}
        <linearGradient
          id="cella-secondary-grad"
          x1="8"
          y1="18"
          x2="28"
          y2="10"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0%" stopColor="#A855F7" />
          <stop offset="100%" stopColor="#06B6D4" />
        </linearGradient>

        {/* Subtle glow filter */}
        <filter id="cella-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="1" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>

      {/* Background soft glow aura */}
      <circle
        cx="18"
        cy="18"
        r="14"
        fill="url(#cella-primary-grad)"
        opacity="0.12"
      />

      {/* Main outer cellular 'C' ribbon loop */}
      <path
        d="M26.5 10.2C24.1 7.6 20.8 6 17 6C10.4 6 5 11.4 5 18C5 24.6 10.4 30 17 30C21.1 30 24.7 28 27 24.8"
        stroke="url(#cella-primary-grad)"
        strokeWidth="3.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Inner intertwined DNA/cellular ribbon forming the 3D 'C' fold */}
      <path
        d="M27.5 12C28.2 14.5 28.5 17 28 19.5C27 23.5 23.5 26.5 19 26.5C14.3 26.5 10.5 22.7 10.5 18C10.5 13.3 14.3 9.5 19 9.5C21.5 9.5 23.8 10.6 25.4 12.3"
        stroke="url(#cella-secondary-grad)"
        strokeWidth="2.4"
        strokeLinecap="round"
        opacity="0.88"
      />

      {/* Center cellular core nucleus */}
      <circle
        cx="18.5"
        cy="17.5"
        r="3"
        fill="url(#cella-primary-grad)"
      />
      <circle
        cx="19.5"
        cy="16.5"
        r="1"
        fill="#FFFFFF"
        opacity="0.9"
      />
    </svg>
  );
}

