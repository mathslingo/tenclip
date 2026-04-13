# version: 1.0
import gradio as gr
from moviepy.video.io.VideoFileClip import VideoFileClip
import tempfile
import os
import traceback

def trim_video(video_file, start_time, end_time):
    if video_file is None:
        raise gr.Error("未选择视频文件")
    
    # 调试输出
    print(f"视频文件路径: {video_file}")
    print(f"开始时间: {start_time}, 结束时间: {end_time}")
    
    try:
        # 检查文件是否存在
        if not os.path.exists(video_file):
            raise FileNotFoundError(f"视频文件不存在: {video_file}")
        
        clip = VideoFileClip(video_file)
        duration = clip.duration
        print(f"视频时长: {duration}秒")
        
        # 边界保护
        start_time = max(0, start_time)
        end_time = min(end_time, duration)
        
        if end_time <= start_time:
            raise ValueError(f"结束时间必须大于开始时间，当前: {start_time} -> {end_time}")
        
        # 执行剪辑
        subclip = clip.subclipped(start_time, end_time)
        
        # 使用自定义临时文件（避免权限问题）
        output_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
        print(f"输出路径: {output_path}")
        
        # 写入视频，增加编码参数
        subclip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            ffmpeg_params=['-preset', 'ultrafast']
        )
        
        # 关闭资源
        clip.close()
        subclip.close()
        
        return output_path
    
    except Exception as e:
        print(f"剪辑失败: {traceback.format_exc()}")
        raise gr.Error(f"剪辑失败: {str(e)}")
    

# 构建 Gradio 界面
with gr.Blocks(title="视频剪辑工具", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🎬 视频剪辑助手")
    gr.Markdown("上传视频，输入开始/结束时间（秒），即可快速剪辑下载。")
    
    with gr.Row():
        with gr.Column(scale=1):
            video_input = gr.Video(label="📁 上传视频", interactive=True)
            with gr.Row():
                start = gr.Number(label="⏱️ 开始时间（秒）", value=0, minimum=0, step=1)
                end = gr.Number(label="⏱️ 结束时间（秒）", value=10, minimum=1, step=1)
            submit_btn = gr.Button("✂️ 开始剪辑", variant="primary", size="lg")
        
        with gr.Column(scale=1):
            video_output = gr.Video(label="✨ 剪辑结果", interactive=False)
    
    submit_btn.click(
        fn=trim_video,
        inputs=[video_input, start, end],
        outputs=video_output
    )
    
    gr.Markdown("---\n💡 **提示**：支持 MP4、MOV 等常见格式，剪辑后可直接下载。")

if __name__ == "__main__":
    demo.launch()