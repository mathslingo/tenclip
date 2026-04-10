import gradio as gr
import tempfile

def test_input(x):
    print(f"Type: {type(x)}")
    print(f"Value: {x}")
    if hasattr(x, 'name'):
        print(f".name: {x.name}")
    return x

iface = gr.Interface(fn=test_input, inputs=gr.File(), outputs=gr.Textbox())
iface.launch(debug=False, share=False, server_port=7861)