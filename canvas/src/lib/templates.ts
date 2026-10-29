import type { Orientation, VoiceChoice } from '../api/types'

export interface IdeaTemplate {
  id: string; icon: string; name: string; hint: string
  target_s: number; orientation: Orientation; voice: VoiceChoice
  /** A fill-in skeleton: the [brackets] are what the user replaces. */
  text: string
}

/** Starting points that already carry what works for each kind of film (length, frame, voice, structure). */
export const IDEA_TEMPLATES: IdeaTemplate[] = [
  { id: 'ad', icon: '🛍', name: 'Quảng cáo sản phẩm', hint: '30s · 9:16 · lồng tiếng', target_s: 30, orientation: 'VERTICAL', voice: 'voiceover',
    text: 'Quảng cáo [tên sản phẩm]. [Người bán / người dùng: tuổi, phong cách] giới thiệu sản phẩm ở [bối cảnh]. '
      + 'Lồng tiếng: câu mở thu hút, [công dụng chính], [điểm khác biệt], lời kêu gọi mua. Kết bằng cận sản phẩm.' },
  { id: 'review', icon: '⭐', name: 'Review / unbox', hint: '40s · 9:16 · nhân vật nói', target_s: 40, orientation: 'VERTICAL', voice: 'dialogue',
    text: '[Nhân vật] mở hộp và review [sản phẩm] trước camera ở [bối cảnh]: cảm nhận đầu tiên, dùng thử, nhận xét thật, kết luận có nên mua.' },
  { id: 'fmv', icon: '💞', name: 'Phim tình cảm (FMV)', hint: '60s · 16:9 · không lời', target_s: 60, orientation: 'HORIZONTAL', voice: 'none',
    text: '[Hai nhân vật] [làm việc gì cùng nhau] ở [bối cảnh]. Mở đầu vui, [biến cố], kết [buồn / ấm áp]. Vật kỷ niệm: [đồ vật].' },
  { id: 'vlog', icon: '📹', name: 'Vlog một ngày', hint: '45s · 9:16 · lồng tiếng', target_s: 45, orientation: 'VERTICAL', voice: 'voiceover',
    text: 'Một ngày của [nhân vật] ở [nơi]: buổi sáng [việc], buổi trưa [việc], buổi tối [việc]. Giọng kể nhẹ nhàng, chân thật.' },
  { id: 'howto', icon: '🍳', name: 'Hướng dẫn / công thức', hint: '60s · 9:16 · lồng tiếng', target_s: 60, orientation: 'VERTICAL', voice: 'voiceover',
    text: 'Hướng dẫn [làm món / việc gì] trong [số] bước ở [bối cảnh]. Mỗi bước một cận tay rõ ràng, lồng tiếng đọc từng bước, kết bằng thành phẩm.' },
]
