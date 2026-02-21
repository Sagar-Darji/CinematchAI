import Joyride, { type CallBackProps, STATUS, type Step } from 'react-joyride'
import { useUserStore } from '@/store/useUserStore'

const TOUR_STEPS: Step[] = [
  {
    target: '#tour-logo',
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 6 }}>Welcome to CineMatch AI 🎬</h3>
        <p style={{ margin: 0, lineHeight: 1.6 }}>
          Your AI-powered cinema companion. Let's take a quick tour of everything you can do here.
        </p>
      </div>
    ),
    placement: 'right',
    disableBeacon: true,
  },
  {
    target: '#tour-nav-for-you',
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 6 }}>For You ✨</h3>
        <p style={{ margin: 0, lineHeight: 1.6 }}>
          Get personalised movie recommendations powered by a multi-agent AI pipeline — tailored to your taste, mood, and context.
        </p>
      </div>
    ),
    placement: 'right',
    disableBeacon: true,
  },
  {
    target: '#tour-nav-discover',
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 6 }}>Discover 🔍</h3>
        <p style={{ margin: 0, lineHeight: 1.6 }}>
          Browse and search through thousands of films across 20+ languages. Filter by genre, year, rating, and more.
        </p>
      </div>
    ),
    placement: 'right',
    disableBeacon: true,
  },
  {
    target: '#tour-nav-cineweb',
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 6 }}>CineWeb 🕸️</h3>
        <p style={{ margin: 0, lineHeight: 1.6 }}>
          Explore an interactive graph that maps how movies connect through directors, actors, genres, and themes.
        </p>
      </div>
    ),
    placement: 'right',
    disableBeacon: true,
  },
  {
    target: '#tour-nav-cinedigest',
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 6 }}>CineDigest 📰</h3>
        <p style={{ margin: 0, lineHeight: 1.6 }}>
          Stay up-to-date with the latest cinema news, reviews, and curated editorial picks.
        </p>
      </div>
    ),
    placement: 'right',
    disableBeacon: true,
  },
  {
    target: '#tour-nav-releases',
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 6 }}>Release Calendar 📅</h3>
        <p style={{ margin: 0, lineHeight: 1.6 }}>
          Track upcoming releases so you never miss a film you're excited about.
        </p>
      </div>
    ),
    placement: 'right',
    disableBeacon: true,
  },
  {
    target: '#tour-nav-profile',
    content: (
      <div>
        <h3 style={{ fontWeight: 700, marginBottom: 6 }}>Your Profile 👤</h3>
        <p style={{ margin: 0, lineHeight: 1.6 }}>
          View your watch history, ratings, and fine-tune your taste profile to improve recommendations over time.
        </p>
      </div>
    ),
    placement: 'right',
    disableBeacon: true,
  },
]

const TOUR_STYLES = {
  options: {
    primaryColor: '#e5c040',
    backgroundColor: '#1a1a2e',
    textColor: '#e8e8f0',
    arrowColor: '#1a1a2e',
    overlayColor: 'rgba(0, 0, 0, 0.55)',
    zIndex: 9999,
  },
  tooltip: {
    borderRadius: 12,
    padding: '18px 20px',
    border: '1px solid rgba(255,255,255,0.08)',
    maxWidth: 300,
  },
  tooltipTitle: { display: 'none' },
  buttonNext: {
    backgroundColor: '#e5c040',
    color: '#0a0a0f',
    borderRadius: 8,
    fontWeight: 700,
    fontSize: 13,
    padding: '8px 16px',
  },
  buttonBack: {
    color: '#9898b0',
    fontWeight: 600,
    fontSize: 13,
  },
  buttonSkip: {
    color: '#9898b0',
    fontSize: 12,
  },
}

export function UserTour() {
  const { isOnboarded, userId, hasSeenTour, setHasSeenTour } = useUserStore()

  const shouldRun = isOnboarded && !!userId && !hasSeenTour

  const handleCallback = (data: CallBackProps) => {
    const { status } = data
    if (status === STATUS.FINISHED || status === STATUS.SKIPPED) {
      setHasSeenTour(true)
    }
  }

  if (!shouldRun) return null

  return (
    <Joyride
      steps={TOUR_STEPS}
      run={shouldRun}
      continuous
      showSkipButton
      showProgress
      scrollToFirstStep
      callback={handleCallback}
      styles={TOUR_STYLES}
      locale={{
        back: 'Back',
        close: 'Close',
        last: 'Done',
        next: 'Next',
        skip: 'Skip tour',
      }}
    />
  )
}
