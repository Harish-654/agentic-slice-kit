import type { FC } from 'react'
import { LogOutIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/useAuth'

export const SignOutButton: FC = () => {
  const { signOut } = useAuth()
  return (
    <Button variant="ghost" size="sm" onClick={() => void signOut()} title="Sign out">
      <LogOutIcon />
      <span className="hidden sm:inline">Sign out</span>
      <span className="sr-only sm:hidden">Sign out</span>
    </Button>
  )
}
